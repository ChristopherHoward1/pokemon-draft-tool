"""Finished draft exports derived from the engine pick log."""

import csv
from io import StringIO

from engine.draft_state import DraftState
from server.session_manager import NotReady, Session

_LABELS = {"aaa": "AAA", "pokebilities": "Pokébilities"}
_DISCORD_ESCAPES = str.maketrans({char: f"\\{char}" for char in "*_~`|\\@"})


def require_complete(session: Session) -> DraftState:
    state = session.state
    if state is None or not state.is_complete():
        raise NotReady("Draft is not complete")
    return state


def results_csv(session: Session) -> str:
    state = require_complete(session)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("pick", "round", "team", "pokemon", "slug", "tier", "cost"))
    for pick in state.pick_log():
        entry = pick["entry"]
        team = pick["team"]
        if team.startswith(("=", "+", "-", "@")):
            team = "'" + team
        writer.writerow((pick["pick"], pick["round"], team, entry["display_name"],
                         entry["name"], entry["vr_tier"], pick["cost"]))
    return output.getvalue()


def results_text(session: Session) -> str:
    state = require_complete(session)
    lines = [f"**{_LABELS[session.config.format]} draft — {session.id}**"]
    teams = state.export()["teams"]
    for name in session.slots:
        team = teams[name]
        picks = ", ".join(
            f"{entry['display_name']} {'U' if entry['vr_tier'] == 'Unranked' else entry['vr_tier']}"
            for entry in team["roster"]
        )
        lines.append(f"**{name.translate(_DISCORD_ESCAPES)}** ({team['remaining_budget']} left): {picks}")
    return "\n".join(lines)
