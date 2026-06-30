from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.draft_state import DraftState
from engine.pool import DraftPool

_REPO_ROOT = Path(__file__).parent.parent

_FORMAT_KEYS = {"AAA": "aaa", "Pokébilities": "pokebilities"}

# Canonical tier order (most expensive first)
_TIER_ORDER = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "Unranked"]

_TYPE_COLORS: dict[str, str] = {
    "normal": "#A8A878", "fire": "#F08030", "water": "#6890F0",
    "electric": "#F8D030", "grass": "#78C850", "ice": "#98D8D8",
    "fighting": "#C03028", "poison": "#A040A0", "ground": "#E0C068",
    "flying": "#A890F0", "psychic": "#F85888", "bug": "#A8B820",
    "rock": "#B8A038", "ghost": "#705898", "dragon": "#7038F8",
    "dark": "#705848", "steel": "#B8B8D0", "fairy": "#EE99AC",
}

_TIER_COLORS: dict[str, str] = {
    "S":  "#C62828",
    "A+": "#E65100", "A": "#E65100", "A-": "#E65100",
    "B+": "#1565C0", "B": "#1565C0", "B-": "#1565C0",
    "C+": "#546E7A", "C": "#546E7A",
    "D":  "#455A64",
    "Unranked": "#37474F",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_data
def _roster_stats(format_key: str) -> dict:
    pool = DraftPool(format_key)
    entries = list(pool._all.values())
    ranked = [e for e in entries if e["vr_tier"] != "Unranked"]
    unranked = [e for e in entries if e["vr_tier"] == "Unranked"]
    return {"total": len(entries), "ranked": len(ranked), "unranked": len(unranked)}


def _type_badge(t: str) -> str:
    color = _TYPE_COLORS.get(t, "#999")
    return (
        f'<span style="background:{color};color:#fff;padding:1px 7px;'
        f'border-radius:9px;font-size:11px;white-space:nowrap">{t.title()}</span>'
    )


def _tier_badge(tier: str, cost: int) -> str:
    color = _TIER_COLORS.get(tier, "#555")
    return (
        f'<span style="background:{color};color:#fff;padding:1px 6px;'
        f'border-radius:4px;font-size:11px;font-weight:bold">{tier}</span>'
        f'&nbsp;<span style="font-size:12px;color:#888">{cost} pts</span>'
    )


def _inline_tier(tier: str) -> str:
    color = _TIER_COLORS.get(tier, "#555")
    return (
        f'<span style="background:{color};color:#fff;padding:1px 5px;'
        f'border-radius:3px;font-size:10px">{tier}</span>'
    )


def _inject_css() -> None:
    st.markdown(
        "<style>button[disabled]{opacity:.4!important;cursor:default!important}</style>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Setup screen
# ---------------------------------------------------------------------------

def _setup_screen() -> None:
    st.title("Pokemon Draft Tool")

    col, _ = st.columns([2, 3])
    with col:
        st.subheader("Format")
        format_label = st.radio(
            "Format",
            list(_FORMAT_KEYS),
            index=None,
            label_visibility="collapsed",
        )
        format_key = _FORMAT_KEYS.get(format_label)

        st.divider()

        st.subheader("Teams")
        team_count = st.slider("Number of teams", min_value=2, max_value=8, value=4)
        team_names: list[str] = []
        for i in range(team_count):
            raw = st.text_input(
                f"Team {i + 1}", key=f"team_{i}", placeholder=f"Team {i + 1}"
            )
            team_names.append(raw.strip())

        st.divider()

        st.subheader("Pool")
        pool_mode_label = st.radio(
            "Generation mode",
            ["Full Random", "VR-Weighted"],
            index=None,
        )

        pool_params: dict = {}
        if pool_mode_label and format_key:
            stats = _roster_stats(format_key)
            if pool_mode_label == "Full Random":
                size = st.number_input(
                    "Pool size",
                    min_value=1,
                    max_value=stats["total"],
                    value=min(120, stats["total"]),
                    step=1,
                )
                pool_params = {"mode": "random", "size": int(size)}
            else:
                vr_count = st.number_input(
                    "VR-ranked Pokemon",
                    min_value=1,
                    max_value=stats["ranked"],
                    value=min(60, stats["ranked"]),
                    step=1,
                )
                unranked_count = st.number_input(
                    "Unranked Pokemon",
                    min_value=1,
                    max_value=stats["unranked"],
                    value=min(60, stats["unranked"]),
                    step=1,
                )
                pool_params = {
                    "mode": "vr_weighted",
                    "vr_count": int(vr_count),
                    "unranked_count": int(unranked_count),
                }
        elif pool_mode_label and not format_key:
            st.caption("Select a format above to configure pool size.")

        st.divider()

        issues: list[str] = []
        if not format_key:
            issues.append("choose a format")
        if not pool_mode_label:
            issues.append("choose a generation mode")
        blank = [i + 1 for i, n in enumerate(team_names) if not n]
        if blank:
            lbl = "name" if len(blank) == 1 else "names"
            issues.append(f"fill team {lbl}: {', '.join(str(i) for i in blank)}")
        filled = [n for n in team_names if n]
        if len(set(filled)) < len(filled):
            issues.append("team names must be unique")

        if issues:
            st.caption("Still needed: " + "  \xb7  ".join(issues))

        if st.button("Confirm and generate pool", disabled=bool(issues), type="primary"):
            with st.spinner("Generating pool…"):
                pool = DraftPool(format_key)
                pool.generate_pool(**pool_params)
                state = DraftState(pool, team_names)

            # Snapshot the full pool sorted by tier-cost desc then name — taken at
            # confirm time so taken cards remain visible in the grid after they're drafted.
            full_pool = pool.available()
            costs = pool._config["tier_costs"]
            full_pool.sort(
                key=lambda e: (-costs.get(e["vr_tier"], 0), e["name"])
            )

            st.session_state.draft = state
            st.session_state.pool = pool
            st.session_state.format_label = format_label
            st.session_state.full_pool = full_pool
            st.session_state.draft_log = []
            st.rerun()


# ---------------------------------------------------------------------------
# Draft board — sidebar
# ---------------------------------------------------------------------------

def _render_sidebar(state: DraftState, pool: DraftPool, export: dict) -> None:
    config = pool._config
    format_label = st.session_state.get("format_label", "")

    st.header("Draft Info")
    st.caption(
        f"**{format_label}**  ·  {config['budget']} pt budget"
        f"  ·  {config['roster_size']} picks/team"
    )

    st.divider()

    if export["complete"]:
        st.success("Draft complete!")
    else:
        current = export["current_team"]
        team_data = export["teams"][current]
        picks_made = team_data["picks_made"]
        roster_size = config["roster_size"]
        remaining = team_data["remaining_budget"]

        st.subheader(current)
        c1, c2 = st.columns(2)
        c1.metric("Pick", f"{picks_made + 1} / {roster_size}")
        c2.metric("Budget", f"{remaining} pts")

    st.divider()

    can_undo = bool(st.session_state.get("draft_log"))
    if st.button("Undo last pick", disabled=not can_undo, use_container_width=True, type="primary"):
        try:
            state.undo()
            st.session_state.draft_log.pop()
            st.session_state.pop("pick_error", None)
        except RuntimeError:
            pass
        st.rerun()

    st.divider()

    if st.button("Export draft JSON", use_container_width=True):
        exports_dir = _REPO_ROOT / "exports"
        exports_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = format_label.lower().replace(" ", "_").replace("\xe9", "e")
        path = exports_dir / f"draft_{slug}_{ts}.json"
        data = export.copy()
        data["format"] = format_label
        data["exported_at"] = ts
        path.write_text(json.dumps(data, indent=2))
        st.success(f"Saved: `{path.relative_to(_REPO_ROOT)}`")

    st.divider()

    st.subheader("Pick history")
    log = st.session_state.get("draft_log", [])
    if not log:
        st.caption("No picks yet.")
    else:
        with st.container(height=300):
            for entry in reversed(log):
                st.markdown(
                    f'**{entry["team"]}** → {entry["pokemon"]} '
                    f'{_inline_tier(entry["tier"])} '
                    f'<span style="font-size:11px;color:#888">−{entry["cost"]} pts</span>',
                    unsafe_allow_html=True,
                )

    st.divider()
    if st.button("Reset draft", use_container_width=True):
        for key in ("draft", "pool", "format_label", "full_pool", "draft_log", "pick_error"):
            st.session_state.pop(key, None)
        st.rerun()


# ---------------------------------------------------------------------------
# Draft board — pool grid
# ---------------------------------------------------------------------------

def _render_pool_grid(state: DraftState, pool: DraftPool, export: dict) -> None:
    full_pool: list[dict] = st.session_state.get("full_pool", [])
    available_names = {e["name"] for e in pool.available()}
    is_complete = export["complete"]

    # Filter row
    fc1, fc2, fc3 = st.columns([2, 1.5, 1.5])
    with fc1:
        search = st.text_input(
            "Search", placeholder="Search by name…",
            label_visibility="collapsed", key="grid_search",
        )
    with fc2:
        all_types = sorted({t for e in full_pool for t in e["types"]})
        type_filter = st.multiselect(
            "Type", all_types, placeholder="All types",
            label_visibility="collapsed", key="grid_type",
        )
    with fc3:
        present_tiers = [t for t in _TIER_ORDER if any(e["vr_tier"] == t for e in full_pool)]
        tier_filter = st.multiselect(
            "Tier", present_tiers, placeholder="All tiers",
            label_visibility="collapsed", key="grid_tier",
        )

    # Apply filters
    visible = full_pool
    if search:
        q = search.lower()
        visible = [e for e in visible if q in e["display_name"].lower() or q in e["name"].lower()]
    if type_filter:
        visible = [e for e in visible if any(t in type_filter for t in e["types"])]
    if tier_filter:
        visible = [e for e in visible if e["vr_tier"] in tier_filter]

    n_avail = sum(1 for e in visible if e["name"] in available_names)
    n_taken = len(visible) - n_avail
    st.caption(
        f"{n_avail} available  ·  {n_taken} taken"
        + (f"  ·  showing {len(visible)} of {len(full_pool)}" if len(visible) < len(full_pool) else "")
    )

    if "pick_error" in st.session_state:
        st.error(f"Cannot draft: {st.session_state.pick_error}")

    if is_complete:
        st.success("All rosters are full. Draft complete!")

    # 4-column card grid
    cols_per_row = 4
    for row_start in range(0, len(visible), cols_per_row):
        row_entries = visible[row_start : row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for j, entry in enumerate(row_entries):
            name = entry["name"]
            is_avail = name in available_names
            tier = entry["vr_tier"]
            cost = pool.tier_cost(tier)
            sprite = _REPO_ROOT / entry.get("sprite_path", f"sprites/{entry['dex_id']}.png")

            with cols[j]:
                with st.container(border=True):
                    if sprite.exists():
                        st.image(str(sprite), width=80)

                    st.markdown(f"**{entry['display_name']}**")

                    badges = " ".join(_type_badge(t) for t in entry["types"])
                    st.markdown(
                        badges + "<br>" + _tier_badge(tier, cost),
                        unsafe_allow_html=True,
                    )

                    if is_avail and not is_complete:
                        if st.button("Draft", key=f"pick_{name}", use_container_width=True):
                            team_before = state.current_team()
                            result = state.pick(name)
                            if result.valid:
                                st.session_state.draft_log.append({
                                    "team": team_before,
                                    "pokemon": entry["display_name"],
                                    "tier": tier,
                                    "cost": cost,
                                })
                                st.session_state.pop("pick_error", None)
                            else:
                                st.session_state.pick_error = result.reason
                            st.rerun()
                    else:
                        btn_label = "TAKEN" if not is_avail else "Draft complete"
                        st.button(
                            btn_label, key=f"taken_{name}",
                            disabled=True, use_container_width=True,
                        )


# ---------------------------------------------------------------------------
# Draft board — team roster tabs
# ---------------------------------------------------------------------------

def _render_team_rosters(pool: DraftPool, export: dict) -> None:
    st.divider()
    st.subheader("Team Rosters")

    config = pool._config
    team_names = list(export["teams"].keys())
    tabs = st.tabs(team_names)

    for tab, team_name in zip(tabs, team_names):
        with tab:
            team_data = export["teams"][team_name]
            roster = team_data["roster"]
            picks_made = team_data["picks_made"]
            remaining = team_data["remaining_budget"]
            roster_size = config["roster_size"]

            st.caption(f"{picks_made} / {roster_size} picks  ·  {remaining} pts remaining")

            if not roster:
                st.caption("No picks yet.")
                continue

            slots_per_row = 5
            for row_start in range(0, len(roster), slots_per_row):
                row = roster[row_start : row_start + slots_per_row]
                rcols = st.columns(slots_per_row)
                for j, entry in enumerate(row):
                    tier = entry["vr_tier"]
                    cost = pool.tier_cost(tier)
                    sprite = _REPO_ROOT / entry.get(
                        "sprite_path", f"sprites/{entry['dex_id']}.png"
                    )
                    with rcols[j]:
                        if sprite.exists():
                            st.image(str(sprite), width=60)
                        st.markdown(
                            f"**{entry['display_name']}**  \n"
                            f"{_inline_tier(tier)}"
                            f'&nbsp;<span style="font-size:11px;color:#888">{cost} pts</span>',
                            unsafe_allow_html=True,
                        )


# ---------------------------------------------------------------------------
# Draft board entry point
# ---------------------------------------------------------------------------

def _draft_board() -> None:
    _inject_css()
    state: DraftState = st.session_state.draft
    pool: DraftPool = st.session_state.pool
    export = state.export()

    with st.sidebar:
        _render_sidebar(state, pool, export)

    st.header("Available Pool")
    _render_pool_grid(state, pool, export)
    _render_team_rosters(pool, export)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Pokemon Draft Tool", layout="wide")
    if "draft" not in st.session_state:
        _setup_screen()
    else:
        _draft_board()


if __name__ == "__main__":
    main()
