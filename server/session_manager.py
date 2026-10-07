"""In-memory draft session store; started rooms can be snapshotted to store_dir.

This module owns session state and engine orchestration only; WebSocket
connection tracking and broadcasting live in ``main.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from engine.draft_state import DraftState
from engine.pool import DraftPool
from server.models import CreateSessionRequest

# Room codes: 6 chars from an unambiguous alphabet (no 0/O/1/I).
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LEN = 6
_LOG = logging.getLogger("uvicorn.error")


class SessionError(Exception):
    """Base for all session-level errors; carries an HTTP-ish status."""

    status_code = 400


class SessionNotFound(SessionError):
    status_code = 404


class SessionFull(SessionError):
    status_code = 409


class NameTaken(SessionError):
    status_code = 409


class AlreadyStarted(SessionError):
    status_code = 409


class NotReady(SessionError):
    status_code = 409


@dataclass
class Session:
    id: str
    config: CreateSessionRequest
    slots: list[str] = field(default_factory=list)  # team names in join order
    started: bool = False
    pool: DraftPool | None = None
    state: DraftState | None = None
    # Serializes pick/undo so two clients can't mutate state concurrently.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # -- lobby -----------------------------------------------------------

    def slot_of(self, team_name: str) -> int | None:
        """1-based slot index for a team name, or None if not joined."""
        for i, name in enumerate(self.slots):
            if name == team_name:
                return i + 1
        return None

    def slot_infos(self) -> list[dict]:
        return [{"slot": i + 1, "team_name": n} for i, n in enumerate(self.slots)]

    def is_full(self) -> bool:
        return len(self.slots) >= self.config.num_teams

    # -- state payload ---------------------------------------------------

    def config_payload(self) -> dict:
        c = self.config
        return {
            "session_id": self.id,
            "format": c.format,
            "num_teams": c.num_teams,
            "draft_order": c.draft_order,
            "budget": c.budget,
            "roster_size": c.roster_size,
            "pool_mode": c.pool_mode,
        }

    def state_payload(self) -> dict:
        """Full draft snapshot for a ``state_update`` message.

        Merges DraftState.export() with session config, slot order, and the
        complete generated pool (each entry flagged taken/available) so the
        client can render the grid without extra round-trips.
        """
        if self.state is None or self.pool is None:
            raise NotReady("Draft has not started")

        export = self.state.export()
        available = {e["name"] for e in self.pool.available()}
        costs = self.pool._config["tier_costs"]

        entries = list(self.pool._pool.values())
        entries.sort(key=lambda e: (-costs.get(e["vr_tier"], 0), e["name"]))
        pool_view = [
            {
                "dex_id": e["dex_id"],
                "name": e["name"],
                "display_name": e["display_name"],
                "types": e["types"],
                "vr_tier": e["vr_tier"],
                "sprite_path": e.get("sprite_path", f"sprites/{e['dex_id']}.png"),
                "cost": self.pool.tier_cost(e["vr_tier"]),
                "taken": e["name"] not in available,
            }
            for e in entries
        ]

        return {
            **export,
            "config": self.config_payload(),
            "slots": self.slot_infos(),
            "pool": pool_view,
        }


class SessionManager:
    def __init__(self, store_dir: Path | None = None) -> None:
        self._sessions: dict[str, Session] = {}
        self.store_dir = store_dir
        if store_dir is not None:
            self._load_all()

    # -- lifecycle -------------------------------------------------------

    def create(self, config: CreateSessionRequest) -> Session:
        code = self._new_code()
        session = Session(id=code, config=config)
        self._sessions[code] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id.upper())
        if session is None:
            raise SessionNotFound(f"No session {session_id!r}")
        return session

    def join(self, session_id: str, team_name: str) -> int:
        session = self.get(session_id)
        name = team_name.strip()
        if not name:
            raise SessionError("Team name cannot be empty")
        if session.started:
            raise AlreadyStarted("Draft already started")
        if session.is_full():
            raise SessionFull("All slots are filled")
        if name in session.slots:
            raise NameTaken(f"Team name {name!r} is already taken")
        session.slots.append(name)
        return len(session.slots)  # 1-based slot index

    def start(self, session_id: str) -> Session:
        session = self.get(session_id)
        if session.started:
            raise AlreadyStarted("Draft already started")
        if not session.is_full():
            raise NotReady(
                f"Need {session.config.num_teams} teams, have {len(session.slots)}"
            )

        pool = self._build_pool(session.config)
        self._apply_overrides(pool, session.config)

        state = DraftState(pool, session.slots, draft_order=session.config.draft_order)
        session.pool = pool
        session.state = state
        session.started = True
        self.save(session)
        return session

    def save(self, session: Session) -> None:
        if self.store_dir is None or not session.started:
            return
        assert session.pool is not None and session.state is not None
        snapshot = {
            "version": 1,
            "id": session.id,
            "config": session.config.model_dump(),
            "slots": session.slots,
            "pool": list(session.pool._pool),
            "rosters": {
                name: [entry["name"] for entry in team["roster"]]
                for name, team in session.state.export()["teams"].items()
            },
            "can_undo": session.state.can_undo(),
        }
        temp_path: Path | None = None
        try:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.store_dir,
                                             suffix=".tmp", delete=False) as temp:
                temp_path = Path(temp.name)
                json.dump(snapshot, temp)
                # Flush to disk so a power loss can't leave a truncated file
                # behind the atomic rename.
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, self.store_dir / f"{session.id}.json")
        except OSError as exc:
            _LOG.warning("Could not save draft room %s: %s", session.id, exc)
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError as exc:
                    _LOG.warning("Could not remove draft temp file %s: %s", temp_path, exc)

    def _load_all(self) -> None:
        assert self.store_dir is not None
        try:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            files = sorted(self.store_dir.glob("*.json"))
        except OSError as exc:
            _LOG.warning("Could not load draft rooms from %s: %s", self.store_dir, exc)
            return
        restored = []
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data["version"] != 1:
                    raise ValueError(f"Unknown version {data['version']!r}")
                if data["id"] != path.stem or not isinstance(data["id"], str):
                    raise ValueError("Room ID does not match filename")
                config = CreateSessionRequest(**data["config"])
                slots = data["slots"]
                if (not isinstance(slots, list) or len(slots) != config.num_teams
                        or any(not isinstance(name, str) or not name.strip() for name in slots)
                        or len(set(slots)) != len(slots)):
                    raise ValueError("Invalid slots")
                names = data["pool"]
                rosters = data["rosters"]
                if (not isinstance(names, list) or not all(isinstance(n, str) for n in names)
                        or not isinstance(rosters, dict)
                        or any(not isinstance(v, list) or
                               not all(isinstance(n, str) for n in v) for v in rosters.values())
                        or not isinstance(data["can_undo"], bool)):
                    raise ValueError("Invalid draft snapshot")
                pool = DraftPool(config.format)
                pool.load_pool(names)
                self._apply_overrides(pool, config)
                state = DraftState(pool, slots, draft_order=config.draft_order)
                state.restore(rosters, data["can_undo"])
                session = Session(id=data["id"], config=config, slots=slots,
                                  started=True, pool=pool, state=state)
                self._sessions[session.id] = session
                restored.append(session.id)
            except (OSError, ValueError, TypeError, KeyError, ValidationError) as exc:
                _LOG.warning("Skipping draft room file %s: %s", path, exc)
        if restored:
            _LOG.info("Restored %d draft room(s): %s", len(restored), ", ".join(restored))

    @staticmethod
    def _apply_overrides(pool: DraftPool, config: CreateSessionRequest) -> None:
        pool._config = dict(pool._config)
        pool._config["budget"] = config.budget
        pool._config["roster_size"] = config.roster_size

    # -- helpers ---------------------------------------------------------

    def _build_pool(self, config: CreateSessionRequest) -> DraftPool:
        pool = DraftPool(config.format)
        mode = config.pool_mode
        # generate_pool raises ValueError when a request exceeds what the format
        # has (e.g. vr_count > ranked available) — surface it as a clean 4xx
        # instead of letting it escape as an unhandled 500 on Start.
        try:
            if mode == "random":
                if config.pool_size is None:
                    raise SessionError("random pool mode requires pool_size")
                pool.generate_pool(mode="random", size=config.pool_size)
            elif mode == "vr_weighted":
                if config.vr_count is None or config.unranked_count is None:
                    raise SessionError(
                        "vr_weighted pool mode requires vr_count and unranked_count"
                    )
                pool.generate_pool(
                    mode="vr_weighted",
                    vr_count=config.vr_count,
                    unranked_count=config.unranked_count,
                )
            else:  # stratified
                if not config.tier_counts:
                    raise SessionError("stratified pool mode requires tier_counts")
                pool.generate_pool(mode="stratified", tier_counts=config.tier_counts)
        except ValueError as exc:
            raise SessionError(str(exc)) from exc

        # A pool smaller than every team's full roster would deadlock the draft.
        needed = config.num_teams * config.roster_size
        if len(pool.available()) < needed:
            raise SessionError(
                f"Pool too small: {len(pool.available())} Pokémon for "
                f"{config.num_teams} teams × {config.roster_size} picks "
                f"({needed} needed)"
            )
        return pool

    def _new_code(self) -> str:
        for _ in range(100):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
            if code not in self._sessions:
                return code
        raise RuntimeError("Could not allocate a unique room code")
