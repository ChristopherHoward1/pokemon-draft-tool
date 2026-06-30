from __future__ import annotations

from dataclasses import dataclass, field

from engine.pool import DraftPool


@dataclass(frozen=True)
class PickResult:
    valid: bool
    reason: str = ""


class Validator:
    def __init__(self, pool: DraftPool) -> None:
        self._pool = pool
        self._roster_size: int = pool._config["roster_size"]

    def check(self, name: str, remaining_budget: int, picks_made: int) -> PickResult:
        available_names = {e["name"] for e in self._pool.available()}
        if name not in available_names:
            return PickResult(valid=False, reason=f"{name!r} is not in the available pool")

        if picks_made >= self._roster_size:
            return PickResult(
                valid=False,
                reason=f"roster is full ({picks_made}/{self._roster_size})",
            )

        entry = self._pool.get(name)
        cost = self._pool.tier_cost(entry["vr_tier"])
        if cost > remaining_budget:
            return PickResult(
                valid=False,
                reason=f"insufficient budget: {name!r} costs {cost}, {remaining_budget} remaining",
            )

        return PickResult(valid=True)
