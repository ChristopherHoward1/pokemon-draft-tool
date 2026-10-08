"""Finished draft exports through REST, including restored rooms and undo."""

import csv
import json
from io import StringIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.draft_state import DraftState
from engine.pool import DraftPool
from server import main
from server.models import CreateSessionRequest
from server.results import results_text
from server.session_manager import Session, SessionManager


@pytest.fixture
def manager(monkeypatch, tmp_path):
    manager = SessionManager(store_dir=tmp_path)
    monkeypatch.setattr(main, "manager", manager)
    main.conns.draft.clear()
    return manager


@pytest.fixture
def client():
    with TestClient(main.app) as client:
        yield client


def completed_room(manager, *, names=("Alpha", "Bravo"), format="aaa",
                   roster_size=2, budget=60, pool_names=None):
    config = CreateSessionRequest(format=format, num_teams=len(names), draft_order="snake",
                                  budget=budget, roster_size=roster_size,
                                  pool_mode="random", pool_size=len(names) * roster_size)
    pool = DraftPool(format)
    if pool_names is None:
        pool_names = list(pool._all)[:len(names) * roster_size]
    pool.load_pool(pool_names)
    manager._apply_overrides(pool, config)
    state = DraftState(pool, list(names), draft_order=config.draft_order)
    for name in pool_names:
        assert state.pick(name).valid, name
    assert state.is_complete()
    session = Session(id="ABC234", config=config, slots=list(names), started=True,
                      pool=pool, state=state)
    manager._sessions[session.id] = session
    return session


@pytest.mark.parametrize("suffix", ["csv", "txt"])
def test_unknown_and_incomplete_rooms(client, manager, suffix):
    path = f"/session/ABC234/results.{suffix}"
    assert client.get(path).status_code == 404
    config = CreateSessionRequest(format="aaa", num_teams=2, budget=60,
                                  pool_mode="random", pool_size=4)
    session = Session(id="ABC234", config=config)
    manager._sessions[session.id] = session
    lobby = client.get(path)
    assert lobby.status_code == 409 and lobby.json()["reason"]
    pool = DraftPool("aaa")
    pool.load_pool(list(pool._all)[:4])
    manager._apply_overrides(pool, config)
    session.slots = ["Alpha", "Bravo"]
    session.started = True
    session.pool = pool
    session.state = DraftState(pool, session.slots)
    started = client.get(path)
    assert started.status_code == 409 and started.json()["reason"]


def test_csv_order_columns_cost_and_name_escaping(client, manager):
    session = completed_room(manager, names=('Comma, "Quote"', "=SUM(1)"))
    response = client.get(f"/session/{session.id}/results.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="draft_aaa_ABC234.csv"'
    assert response.text.endswith("\n") and "\r\n" not in response.text
    reader = csv.DictReader(StringIO(response.text))
    assert reader.fieldnames == ["pick", "round", "team", "pokemon", "slug", "tier", "cost"]
    rows = list(reader)
    assert len(rows) == 4
    assert [row["team"] for row in rows] == ['Comma, "Quote"', "'=SUM(1)", "'=SUM(1)", 'Comma, "Quote"']
    assert [row["pick"] for row in rows] == ["1", "2", "3", "4"]
    assert [row["round"] for row in rows] == ["1", "1", "2", "2"]
    for row, pick in zip(rows, session.state.pick_log()):
        assert row["pokemon"] == pick["entry"]["display_name"]
        assert row["slug"] == pick["entry"]["name"]
        assert row["tier"] == pick["entry"]["vr_tier"]
        assert int(row["cost"]) == session.pool.tier_cost(row["tier"])


def test_text_slot_order_tiers_and_markdown(client, manager):
    session = completed_room(manager, names=("*Mew*", "@everyone"), format="pokebilities")
    response = client.get(f"/session/{session.id}/results.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    lines = response.text.splitlines()
    assert lines[0] == "**Pokébilities draft — ABC234**"
    for line, team in zip(lines[1:], session.state._teams):
        escaped = team.name.replace("*", "\\*").replace("@", "\\@")
        picks = ", ".join(f"{e['display_name']} {'U' if e['vr_tier'] == 'Unranked' else e['vr_tier']}"
                          for e in team.roster)
        assert line == f"**{escaped}** ({team.remaining_budget} left): {picks}"
    assert len(lines) == 3


def test_all_discord_team_name_escapes(manager):
    session = completed_room(manager, names=("*_~`|\\@", "Bravo"))
    assert results_text(session).splitlines()[1].startswith("**\\*\\_\\~\\`\\|\\\\\\@**")


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_csv_formula_prefixes(client, manager, prefix):
    session = completed_room(manager, names=(prefix + "Team", "Bravo"))
    rows = list(csv.DictReader(StringIO(client.get(f"/session/{session.id}/results.csv").text)))
    assert rows[0]["team"] == "'" + prefix + "Team"


def test_unranked_is_abbreviated_in_text(manager):
    session = completed_room(manager, pool_names=["abomasnow", "alcremie", "alomomola", "gholdengo"])
    assert "Abomasnow U" in results_text(session)


def test_longest_aaa_room_fits_discord(manager):
    path = Path(__file__).parents[2] / "data" / "aaa_pokemon.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    top80 = sorted(data, key=lambda e: -len(e["display_name"]))[:80]
    names = tuple(f"Team{i}" + "x" * 35 for i in range(8))
    session = completed_room(manager, names=names, roster_size=10,
                             pool_names=[entry["name"] for entry in top80])
    assert results_text(session).startswith("**AAA draft — ABC234**\n")
    assert len(results_text(session)) < 2000


def test_restored_room_exports_match(client, manager, monkeypatch, tmp_path):
    session = completed_room(manager)
    csv_before = client.get(f"/session/{session.id}/results.csv").text
    text_before = client.get(f"/session/{session.id}/results.txt").text
    manager.save(session)
    monkeypatch.setattr(main, "manager", SessionManager(store_dir=tmp_path))
    assert client.get(f"/session/{session.id}/results.csv").text == csv_before
    assert client.get(f"/session/{session.id}/results.txt").text == text_before


def test_host_undo_hides_both_exports(client, manager):
    session = completed_room(manager)
    with client.websocket_connect(f"/session/{session.id}/draft?team_name=Alpha") as ws:
        while ws.receive_json()["type"] != "state_update":
            pass
        ws.send_json({"type": "undo"})
        while True:
            message = ws.receive_json()
            if message["type"] == "state_update" and not message["state"]["complete"]:
                break
    for suffix in ("csv", "txt"):
        response = client.get(f"/session/{session.id}/results.{suffix}")
        assert response.status_code == 409 and response.json()["reason"]
