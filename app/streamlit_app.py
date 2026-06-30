from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.draft_state import DraftState
from engine.pool import DraftPool

_FORMAT_KEYS = {"AAA": "aaa", "Pokébilities": "pokebilities"}


@st.cache_data
def _roster_stats(format_key: str) -> dict:
    pool = DraftPool(format_key)
    entries = list(pool._all.values())
    ranked = [e for e in entries if e["vr_tier"] != "Unranked"]
    unranked = [e for e in entries if e["vr_tier"] == "Unranked"]
    return {"total": len(entries), "ranked": len(ranked), "unranked": len(unranked)}


def _setup_screen() -> None:
    st.title("Pokémon Draft Tool")

    col, _ = st.columns([2, 3])
    with col:
        # ── Format ──────────────────────────────────────────────────────────
        st.subheader("Format")
        format_label = st.radio(
            "Format",
            list(_FORMAT_KEYS),
            index=None,
            label_visibility="collapsed",
        )
        format_key = _FORMAT_KEYS.get(format_label)

        st.divider()

        # ── Teams ───────────────────────────────────────────────────────────
        st.subheader("Teams")
        team_count = st.slider("Number of teams", min_value=2, max_value=8, value=4)
        team_names: list[str] = []
        for i in range(team_count):
            raw = st.text_input(f"Team {i + 1}", key=f"team_{i}", placeholder=f"Team {i + 1}")
            team_names.append(raw.strip())

        st.divider()

        # ── Pool ────────────────────────────────────────────────────────────
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
                    "VR-ranked Pokémon",
                    min_value=1,
                    max_value=stats["ranked"],
                    value=min(60, stats["ranked"]),
                    step=1,
                )
                unranked_count = st.number_input(
                    "Unranked Pokémon",
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

        # ── Validation ──────────────────────────────────────────────────────
        issues: list[str] = []
        if not format_key:
            issues.append("choose a format")
        if not pool_mode_label:
            issues.append("choose a generation mode")
        blank = [i + 1 for i, n in enumerate(team_names) if not n]
        if blank:
            label = "name" if len(blank) == 1 else "names"
            issues.append(f"fill team {label}: {', '.join(str(i) for i in blank)}")
        filled = [n for n in team_names if n]
        if len(set(filled)) < len(filled):
            issues.append("team names must be unique")

        if issues:
            st.caption("Still needed: " + "  ·  ".join(issues))

        if st.button("Confirm and generate pool", disabled=bool(issues), type="primary"):
            with st.spinner("Generating pool…"):
                pool = DraftPool(format_key)
                pool.generate_pool(**pool_params)
                state = DraftState(pool, team_names)
            st.session_state.draft = state
            st.session_state.pool = pool
            st.session_state.format_label = format_label
            st.rerun()


def _draft_board() -> None:
    st.info("Draft board — coming in next step.")
    if st.button("Reset draft"):
        for key in ("draft", "pool", "format_label"):
            st.session_state.pop(key, None)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Pokémon Draft Tool", layout="wide")
    if "draft" not in st.session_state:
        _setup_screen()
    else:
        _draft_board()


if __name__ == "__main__":
    main()
