"""Pydantic models for REST bodies and WebSocket message payloads.

The engine (``engine/``) is untouched; these models describe only the wire
format between the React client and the FastAPI server.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Format = Literal["aaa", "pokebilities"]
PoolMode = Literal["random", "vr_weighted", "stratified"]
DraftOrder = Literal["snake", "linear"]


# ---------------------------------------------------------------------------
# REST — session creation / join
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    """Host-supplied configuration when creating a draft room.

    Pool parameters are mode-dependent and validated in the endpoint:
      - random      → pool_size
      - vr_weighted → vr_count + unranked_count
      - stratified  → tier_counts (group -> count)
    """

    format: Format
    num_teams: int = Field(ge=2, le=8)
    draft_order: DraftOrder = "snake"
    budget: int = Field(gt=0, le=999)
    roster_size: int = Field(default=10, ge=1, le=30)

    pool_mode: PoolMode
    pool_size: Optional[int] = Field(default=None, ge=1)
    vr_count: Optional[int] = Field(default=None, ge=1)
    unranked_count: Optional[int] = Field(default=None, ge=1)
    tier_counts: Optional[dict[str, int]] = None


class CreateSessionResponse(BaseModel):
    session_id: str


class JoinRequest(BaseModel):
    team_name: str = Field(min_length=1, max_length=40)


class JoinResponse(BaseModel):
    slot_index: int  # 1-based; slot 1 is the host equivalent


class SlotInfo(BaseModel):
    slot: int
    team_name: str


class LobbySnapshot(BaseModel):
    """GET /session/{id} — used by clients landing on the lobby."""

    session_id: str
    format: Format
    num_teams: int
    draft_order: DraftOrder
    budget: int
    roster_size: int
    slots: list[SlotInfo]
    started: bool


# ---------------------------------------------------------------------------
# WebSocket — inbound (client -> server) on the draft socket
# ---------------------------------------------------------------------------

class PickMessage(BaseModel):
    type: Literal["pick"]
    pokemon_name: str


class UndoMessage(BaseModel):
    type: Literal["undo"]


# Outbound messages (server -> client) are built as plain dicts in main.py so
# they can freely embed DraftState.export() output; their shapes are:
#
#   { "type": "lobby_update", "slots": [{slot, team_name}, ...], "started": bool }
#   { "type": "draft_started" }
#   { "type": "state_update", "state": { ...export() + config... } }
#   { "type": "error", "reason": str }
#   { "type": "player_connected", "team_name": str }
#   { "type": "player_disconnected", "team_name": str }
