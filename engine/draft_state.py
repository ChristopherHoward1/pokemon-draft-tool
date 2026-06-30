from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.pool import DraftPool
from engine.validator import PickResult, Validator


@dataclass
class _Team:
    name: str
    roster: list[dict] = field(default_factory=list)
    remaining_budget: int = 0


class DraftState:
    def __init__(self, pool: DraftPool, team_names: list[str]) -> None:
        min_t = pool._config["min_teams"]
        max_t = pool._config["max_teams"]
        if not (min_t <= len(team_names) <= max_t):
            raise ValueError(
                f"Team count must be {min_t}–{max_t}, got {len(team_names)}"
            )
        if not pool.available():
            raise ValueError("Pool has no available Pokémon — call generate_pool() first")

        budget = pool._config["budget"]
        self._teams: list[_Team] = [_Team(name=n, remaining_budget=budget) for n in team_names]
        self._team_index: dict[str, int] = {n: i for i, n in enumerate(team_names)}
        self._pool = pool
        self._validator = Validator(pool)
        self._undo_record: Optional[tuple[str, str, int]] = None  # (team_name, pokemon_name, cost)

    # ------------------------------------------------------------------
    # Turn order
    # ------------------------------------------------------------------

    def _total_picks(self) -> int:
        return sum(len(t.roster) for t in self._teams)

    def _team_at(self, total: int) -> _Team:
        n = len(self._teams)
        round_num = total // n
        pos = total % n
        idx = pos if round_num % 2 == 0 else n - 1 - pos
        return self._teams[idx]

    def current_team(self) -> str:
        if self.is_complete():
            raise RuntimeError("Draft is complete — no current team")
        return self._team_at(self._total_picks()).name

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def pick(self, name: str) -> PickResult:
        if self.is_complete():
            return PickResult(valid=False, reason="draft is complete")

        team = self._team_at(self._total_picks())
        result = self._validator.check(name, team.remaining_budget, len(team.roster))
        if not result.valid:
            return result

        entry = self._pool.get(name)
        cost = self._pool.tier_cost(entry["vr_tier"])
        self._pool.remove(name)
        team.roster.append(entry)
        team.remaining_budget -= cost
        self._undo_record = (team.name, name, cost)
        return PickResult(valid=True)

    def undo(self) -> None:
        if self._undo_record is None:
            raise RuntimeError("No pick to undo")
        team_name, pokemon_name, cost = self._undo_record
        team = self._teams[self._team_index[team_name]]
        team.roster.pop()
        team.remaining_budget += cost
        self._pool.restore(pokemon_name)
        self._undo_record = None

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_complete(self) -> bool:
        roster_size = self._pool._config["roster_size"]
        return all(len(t.roster) == roster_size for t in self._teams)

    def export(self) -> dict:
        current = None
        if not self.is_complete():
            current = self._team_at(self._total_picks()).name
        return {
            "complete": self.is_complete(),
            "current_team": current,
            "teams": {
                t.name: {
                    "roster": list(t.roster),
                    "remaining_budget": t.remaining_budget,
                    "picks_made": len(t.roster),
                }
                for t in self._teams
            },
        }
