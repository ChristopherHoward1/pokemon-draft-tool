"""Backend acceptance tests — exercise the FastAPI app in-process.

Covers every item in the Phase 3a acceptance criteria.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.main import app, conns, manager


@pytest.fixture(autouse=True)
def _clean_state():
    # Isolate sessions/connections between tests (module-level singletons).
    manager._sessions.clear()
    conns.lobby.clear()
    conns.draft.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _make_config(num_teams=2, roster_size=2, budget=100, pool_size=30):
    return {
        "format": "aaa",
        "num_teams": num_teams,
        "draft_order": "snake",
        "budget": budget,
        "roster_size": roster_size,
        "pool_mode": "random",
        "pool_size": pool_size,
    }


def _create(client, **kw) -> str:
    resp = client.post("/session", json=_make_config(**kw))
    assert resp.status_code == 200
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# REST — create / join
# ---------------------------------------------------------------------------

def test_create_returns_six_char_code(client):
    sid = _create(client)
    assert len(sid) == 6
    assert sid.isalnum() and sid.isupper()


def test_join_fills_slots_in_order(client):
    sid = _create(client)
    r1 = client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    r2 = client.post(f"/session/{sid}/join", json={"team_name": "Bravo"})
    assert r1.json()["slot_index"] == 1
    assert r2.json()["slot_index"] == 2


def test_join_rejects_duplicate_name(client):
    sid = _create(client)
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    dup = client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    assert dup.status_code == 409


def test_join_rejects_when_full(client):
    sid = _create(client, num_teams=2)
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    client.post(f"/session/{sid}/join", json={"team_name": "Bravo"})
    third = client.post(f"/session/{sid}/join", json={"team_name": "Charlie"})
    assert third.status_code == 409


def test_start_rejected_until_full(client):
    sid = _create(client, num_teams=2)
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    resp = client.post(f"/session/{sid}/start")
    assert resp.status_code == 409


def test_start_with_oversized_pool_returns_clean_error(client):
    # vr_count far exceeds any format's ranked pool → generate_pool raises
    # ValueError, which must surface as a clean 4xx with a reason, not a 500.
    cfg = _make_config(num_teams=2, roster_size=2)
    cfg["pool_mode"] = "vr_weighted"
    cfg["vr_count"] = 1000
    cfg["unranked_count"] = 5
    sid = client.post("/session", json=cfg).json()["session_id"]
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    client.post(f"/session/{sid}/join", json={"team_name": "Bravo"})
    resp = client.post(f"/session/{sid}/start")
    assert resp.status_code == 400, f"expected clean 4xx, got {resp.status_code}"
    assert "reason" in resp.json()


# ---------------------------------------------------------------------------
# Lobby WebSocket
# ---------------------------------------------------------------------------

def test_lobby_ws_broadcasts_on_join(client):
    sid = _create(client)
    with client.websocket_connect(f"/session/{sid}/lobby") as ws:
        initial = ws.receive_json()
        assert initial["type"] == "lobby_update"
        assert initial["slots"] == []

        client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
        update = ws.receive_json()
        assert update["type"] == "lobby_update"
        assert update["slots"] == [{"slot": 1, "team_name": "Alpha"}]


def test_lobby_ws_receives_draft_started(client):
    sid = _create(client, num_teams=2)
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    client.post(f"/session/{sid}/join", json={"team_name": "Bravo"})
    with client.websocket_connect(f"/session/{sid}/lobby") as ws:
        ws.receive_json()  # initial snapshot
        client.post(f"/session/{sid}/start")
        started = ws.receive_json()
        assert started["type"] == "draft_started"


# ---------------------------------------------------------------------------
# Draft flow — picks, turn enforcement, undo
# ---------------------------------------------------------------------------

def _start_two_team_draft(client) -> tuple[str, list[dict]]:
    sid = _create(client, num_teams=2, roster_size=2, budget=100)
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    client.post(f"/session/{sid}/join", json={"team_name": "Bravo"})
    client.post(f"/session/{sid}/start")
    state = client.get(f"/session/{sid}/state").json()
    return sid, state["pool"]


def test_pick_from_correct_team_broadcasts_state(client):
    sid, pool = _start_two_team_draft(client)
    first = pool[0]["name"]
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as a, \
         client.websocket_connect(f"/session/{sid}/draft?team_name=Bravo") as b:
        # Each connection first gets a state_update, then player_connected events.
        a.receive_json()  # initial state
        # Alpha (slot 1) picks first in snake order.
        a.send_json({"type": "pick", "pokemon_name": first})

        # Drain each socket to the state_update that reflects the pick (both
        # clients also have an initial state_update / player_connected in queue).
        def state_after_pick(ws):
            while True:
                m = ws.receive_json()
                if m["type"] == "state_update" and any(
                    e["name"] == first and e["taken"] for e in m["state"]["pool"]
                ):
                    return m["state"]

        state_a = state_after_pick(a)
        state_b = state_after_pick(b)
        assert state_a["current_team"] == "Bravo"  # turn advanced
        assert state_b["current_team"] == "Bravo"  # broadcast reached Bravo too


def test_pick_from_wrong_team_errors_and_state_unchanged(client):
    sid, pool = _start_two_team_draft(client)
    first = pool[0]["name"]
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Bravo") as b:
        b.receive_json()  # initial state
        # Bravo is slot 2 — not their turn in round 1.
        b.send_json({"type": "pick", "pokemon_name": first})
        msg = b.receive_json()
        # Could be a player_connected first if others connect; filter to error.
        while msg["type"] != "error":
            msg = b.receive_json()
        assert "not your turn" in msg["reason"].lower()

    # State unchanged: nothing taken.
    state = client.get(f"/session/{sid}/state").json()
    assert all(not e["taken"] for e in state["pool"])
    assert state["current_team"] == "Alpha"


def test_undo_from_slot_one_succeeds(client):
    sid, pool = _start_two_team_draft(client)
    first = pool[0]["name"]
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as a:
        a.receive_json()  # initial state
        a.send_json({"type": "pick", "pokemon_name": first})

        def next_state(ws):
            while True:
                m = ws.receive_json()
                if m["type"] == "state_update":
                    return m["state"]

        next_state(a)  # after pick
        a.send_json({"type": "undo"})
        state = next_state(a)
        assert state["current_team"] == "Alpha"  # back to Alpha
        assert all(not e["taken"] for e in state["pool"])


def test_undo_from_other_slot_rejected(client):
    sid, pool = _start_two_team_draft(client)
    first = pool[0]["name"]
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as a, \
         client.websocket_connect(f"/session/{sid}/draft?team_name=Bravo") as b:
        a.receive_json()
        a.send_json({"type": "pick", "pokemon_name": first})

        def drain_to(ws, wanted):
            while True:
                m = ws.receive_json()
                if m["type"] == wanted:
                    return m

        drain_to(a, "state_update")  # Alpha's pick landed
        # Bravo (slot 2) attempts undo → rejected.
        b.send_json({"type": "undo"})
        err = drain_to(b, "error")
        assert "slot 1" in err["reason"].lower() or "host" in err["reason"].lower()


def test_draft_ws_rejects_unregistered_team(client):
    sid = _create(client, num_teams=2)
    client.post(f"/session/{sid}/join", json={"team_name": "Alpha"})
    client.post(f"/session/{sid}/join", json={"team_name": "Bravo"})
    client.post(f"/session/{sid}/start")
    with pytest.raises(Exception):
        with client.websocket_connect(f"/session/{sid}/draft?team_name=Ghost") as ws:
            ws.receive_json()
