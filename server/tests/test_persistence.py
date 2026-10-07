"""Started room snapshots through the REST and draft WebSocket handlers."""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from server import main
from server.session_manager import SessionManager


@pytest.fixture
def stored_manager(monkeypatch, tmp_path):
    manager = SessionManager(store_dir=tmp_path)
    monkeypatch.setattr(main, "manager", manager)
    main.conns.lobby.clear()
    main.conns.draft.clear()
    return manager


@pytest.fixture
def client():
    with TestClient(main.app) as client:
        yield client


def create_started(client):
    config = {"format": "aaa", "num_teams": 2, "draft_order": "snake",
              "budget": 100, "roster_size": 2, "pool_mode": "random", "pool_size": 20}
    sid = client.post("/session", json=config).json()["session_id"]
    for team in ("Alpha", "Bravo"):
        assert client.post(f"/session/{sid}/join", json={"team_name": team}).status_code == 200
    return sid


def receive_type(ws, kind):
    while True:
        message = ws.receive_json()
        if message["type"] == kind:
            return message


def test_round_trip_and_lobby_not_saved(stored_manager, client, tmp_path, caplog):
    sid = create_started(client)
    assert list(tmp_path.iterdir()) == []
    assert client.post(f"/session/{sid}/start").status_code == 200
    assert (tmp_path / f"{sid}.json").exists()
    state = client.get(f"/session/{sid}/state").json()
    name = next(entry["name"] for entry in state["pool"] if not entry["taken"])
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as ws:
        receive_type(ws, "state_update")
        ws.send_json({"type": "pick", "pokemon_name": name})
        picked = receive_type(ws, "state_update")["state"]
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        restored = SessionManager(store_dir=tmp_path)
    room = restored.get(sid)
    assert room.state_payload() == picked
    assert room.slots == stored_manager.get(sid).slots
    assert room.started is True
    assert room.config == stored_manager.get(sid).config
    assert any(record.name == "uvicorn.error" and record.levelno == logging.INFO
               and record.message == f"Restored 1 draft room(s): {sid}"
               for record in caplog.records)


def test_undo_restores_without_undo_permission(stored_manager, client, tmp_path, monkeypatch):
    sid = create_started(client)
    client.post(f"/session/{sid}/start")
    name = client.get(f"/session/{sid}/state").json()["pool"][0]["name"]
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as ws:
        receive_type(ws, "state_update")
        ws.send_json({"type": "pick", "pokemon_name": name})
        receive_type(ws, "state_update")
        ws.send_json({"type": "undo"})
        receive_type(ws, "state_update")
    restored = SessionManager(store_dir=tmp_path)
    assert restored.get(sid).state.can_undo() is False
    monkeypatch.setattr(main, "manager", restored)
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as ws:
        receive_type(ws, "state_update")
        ws.send_json({"type": "undo"})
        assert receive_type(ws, "error")["reason"] == "No pick to undo"


def test_bad_files_warn_and_valid_room_loads(stored_manager, client, tmp_path, caplog):
    sid = create_started(client)
    client.post(f"/session/{sid}/start")
    (tmp_path / "garbage.json").write_text("not json")
    (tmp_path / "version.json").write_text(json.dumps({"version": 2}))
    bad = json.loads((tmp_path / f"{sid}.json").read_text())
    bad["id"] = "badslug"
    bad["rosters"]["Alpha"] = ["missing-slug"]
    (tmp_path / "badslug.json").write_text(json.dumps(bad))
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        restored = SessionManager(store_dir=tmp_path)
    assert restored.get(sid).started
    warnings = [record for record in caplog.records
                if record.name == "uvicorn.error" and record.levelno == logging.WARNING]
    assert len(warnings) == 3
    assert all("Skipping draft room file" in record.message for record in warnings)


def test_save_failure_does_not_break_pick(stored_manager, client, monkeypatch, caplog):
    sid = create_started(client)
    client.post(f"/session/{sid}/start")
    name = client.get(f"/session/{sid}/state").json()["pool"][0]["name"]

    def fail_replace(*_args):
        raise OSError("disk full")

    monkeypatch.setattr("server.session_manager.os.replace", fail_replace)
    with client.websocket_connect(f"/session/{sid}/draft?team_name=Alpha") as ws:
        receive_type(ws, "state_update")
        with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
            ws.send_json({"type": "pick", "pokemon_name": name})
            state = receive_type(ws, "state_update")["state"]
    assert any(entry["name"] == name and entry["taken"] for entry in state["pool"])
    assert any(record.name == "uvicorn.error" and "disk full" in record.message
               for record in caplog.records)


def test_main_default_store_is_disabled():
    # conftest removes the shell export before server.main is first imported.
    assert main.manager.store_dir is None
