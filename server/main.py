"""FastAPI app: REST + WebSocket endpoints for the multiplayer draft.

Run locally:  uvicorn server.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.models import (
    CreateSessionRequest,
    CreateSessionResponse,
    JoinRequest,
    JoinResponse,
)
from server.session_manager import SessionError, SessionManager

_REPO_ROOT = Path(__file__).parent.parent

app = FastAPI(title="Pokémon Draft — Multiplayer")

# CORS: Vite dev server + configured production frontend.
_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if (frontend_url := os.environ.get("FRONTEND_URL")):
    _origins.append(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/sprites", StaticFiles(directory=str(_REPO_ROOT / "sprites")), name="sprites")

manager = SessionManager()


@app.exception_handler(SessionError)
async def _session_error_handler(_request, exc: SessionError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"reason": str(exc)})


# ---------------------------------------------------------------------------
# WebSocket connection registry
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self) -> None:
        self.lobby: dict[str, set[WebSocket]] = defaultdict(set)
        # draft socket -> team_name it authenticated as
        self.draft: dict[str, dict[WebSocket, str]] = defaultdict(dict)

    async def _broadcast(self, sockets: list[WebSocket], message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._drop(ws)

    def _drop(self, ws: WebSocket) -> None:
        for peers in self.lobby.values():
            peers.discard(ws)
        for peers in self.draft.values():
            peers.pop(ws, None)

    async def broadcast_lobby(self, sid: str, message: dict) -> None:
        await self._broadcast(list(self.lobby[sid]), message)

    async def broadcast_draft(self, sid: str, message: dict) -> None:
        await self._broadcast(list(self.draft[sid].keys()), message)


conns = ConnectionManager()


def _lobby_update(sid: str) -> dict:
    session = manager.get(sid)
    return {
        "type": "lobby_update",
        "slots": session.slot_infos(),
        "started": session.started,
        "num_teams": session.config.num_teams,
    }


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------

@app.post("/session", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    session = manager.create(body)
    return CreateSessionResponse(session_id=session.id)


@app.get("/session/{session_id}")
async def get_session(session_id: str) -> dict:
    session = manager.get(session_id)
    return {
        **session.config_payload(),
        "slots": session.slot_infos(),
        "started": session.started,
    }


@app.post("/session/{session_id}/join", response_model=JoinResponse)
async def join_session(session_id: str, body: JoinRequest) -> JoinResponse:
    slot_index = manager.join(session_id, body.team_name)
    await conns.broadcast_lobby(session_id.upper(), _lobby_update(session_id))
    return JoinResponse(slot_index=slot_index)


@app.post("/session/{session_id}/start")
async def start_session(session_id: str) -> dict:
    session = manager.start(session_id)
    await conns.broadcast_lobby(session.id, {"type": "draft_started"})
    return {"ok": True}


@app.get("/session/{session_id}/state")
async def get_state(session_id: str) -> dict:
    session = manager.get(session_id)
    return session.state_payload()


# ---------------------------------------------------------------------------
# WebSocket — lobby presence
# ---------------------------------------------------------------------------

@app.websocket("/session/{session_id}/lobby")
async def lobby_ws(websocket: WebSocket, session_id: str) -> None:
    sid = session_id.upper()
    try:
        manager.get(sid)
    except SessionError:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    conns.lobby[sid].add(websocket)
    try:
        await websocket.send_json(_lobby_update(sid))
        while True:
            await websocket.receive_text()  # keepalive; client sends nothing meaningful
    except WebSocketDisconnect:
        pass
    finally:
        conns.lobby[sid].discard(websocket)


# ---------------------------------------------------------------------------
# WebSocket — live draft
# ---------------------------------------------------------------------------

@app.websocket("/session/{session_id}/draft")
async def draft_ws(websocket: WebSocket, session_id: str, team_name: str = "") -> None:
    sid = session_id.upper()
    try:
        session = manager.get(sid)
    except SessionError:
        await websocket.close(code=4404)
        return

    team_name = team_name.strip()
    if session.slot_of(team_name) is None:
        # Not a registered player in this session.
        await websocket.close(code=4403)
        return

    await websocket.accept()
    conns.draft[sid][websocket] = team_name

    # Send current state to the newcomer, announce to the rest.
    if session.started:
        await websocket.send_json({"type": "state_update", "state": session.state_payload()})
    await conns.broadcast_draft(sid, {"type": "player_connected", "team_name": team_name})

    try:
        while True:
            msg = await websocket.receive_json()
            await _handle_draft_message(websocket, session, team_name, msg)
    except WebSocketDisconnect:
        pass
    finally:
        conns.draft[sid].pop(websocket, None)
        await conns.broadcast_draft(
            sid, {"type": "player_disconnected", "team_name": team_name}
        )


async def _handle_draft_message(
    websocket: WebSocket, session, team_name: str, msg: dict
) -> None:
    msg_type = msg.get("type")

    if not session.started or session.state is None:
        await websocket.send_json({"type": "error", "reason": "Draft has not started"})
        return

    if msg_type == "pick":
        async with session.lock:
            if session.state.is_complete():
                await websocket.send_json(
                    {"type": "error", "reason": "Draft is complete"}
                )
                return
            if session.state.current_team() != team_name:
                await websocket.send_json(
                    {"type": "error", "reason": "It's not your turn"}
                )
                return
            result = session.state.pick(msg.get("pokemon_name", ""))
            if not result.valid:
                await websocket.send_json({"type": "error", "reason": result.reason})
                return
            payload = session.state_payload()
        await conns.broadcast_draft(
            session.id, {"type": "state_update", "state": payload}
        )

    elif msg_type == "undo":
        # Only slot 1 (the first joiner / host equivalent) may undo.
        if session.slot_of(team_name) != 1:
            await websocket.send_json(
                {"type": "error", "reason": "Only the host (slot 1) can undo"}
            )
            return
        async with session.lock:
            try:
                session.state.undo()
            except RuntimeError as exc:
                await websocket.send_json({"type": "error", "reason": str(exc)})
                return
            payload = session.state_payload()
        await conns.broadcast_draft(
            session.id, {"type": "state_update", "state": payload}
        )

    else:
        await websocket.send_json(
            {"type": "error", "reason": f"Unknown message type {msg_type!r}"}
        )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
