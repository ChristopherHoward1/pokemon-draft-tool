from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import yaml


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "draft_config.yaml"

# Tier groups for stratified sampling: each key maps to the concrete VR tiers it covers.
TIER_GROUPS: dict[str, list[str]] = {
    "S":        ["S"],
    "A":        ["A+", "A", "A-"],
    "B":        ["B+", "B", "B-"],
    "C":        ["C+", "C"],
    "D":        ["D"],
    "Unranked": ["Unranked"],
}


class DraftPool:
    def __init__(self, format_name: str, config_path: Path = _CONFIG_PATH) -> None:
        with open(config_path) as f:
            self._config = yaml.safe_load(f)

        formats: dict[str, str] = self._config["formats"]
        if format_name not in formats:
            raise ValueError(
                f"Unknown format {format_name!r}. Expected one of: {list(formats)}"
            )

        data_path = Path(__file__).parent.parent / formats[format_name]
        with open(data_path) as f:
            entries: list[dict] = json.load(f)

        # Full format roster keyed by canonical slug
        self._all: dict[str, dict] = {e["name"]: e for e in entries}

        # Populated by generate_pool(); empty until then
        self._pool: dict[str, dict] = {}
        self._available: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Pool generation
    # ------------------------------------------------------------------

    def generate_pool(
        self,
        mode: str = "random",
        size: Optional[int] = None,
        vr_count: Optional[int] = None,
        unranked_count: Optional[int] = None,
        tier_counts: Optional[dict[str, int]] = None,
        seed: Optional[int] = None,
    ) -> None:
        rng = random.Random(seed)

        if mode == "random":
            n = size if size is not None else self._config["default_pool_size"]
            chosen = rng.sample(list(self._all.values()), n)

        elif mode == "vr_weighted":
            if vr_count is None or unranked_count is None:
                raise ValueError(
                    "vr_weighted mode requires both vr_count and unranked_count"
                )
            ranked = [e for e in self._all.values() if e["vr_tier"] != "Unranked"]
            unranked = [e for e in self._all.values() if e["vr_tier"] == "Unranked"]
            if vr_count > len(ranked):
                raise ValueError(
                    f"Requested {vr_count} VR-ranked but only {len(ranked)} available"
                )
            if unranked_count > len(unranked):
                raise ValueError(
                    f"Requested {unranked_count} Unranked but only {len(unranked)} available"
                )
            chosen = rng.sample(ranked, vr_count) + rng.sample(unranked, unranked_count)

        elif mode == "stratified":
            if not tier_counts:
                raise ValueError("stratified mode requires a non-empty tier_counts dict")
            unknown = set(tier_counts) - set(TIER_GROUPS)
            if unknown:
                raise ValueError(
                    f"Unknown tier group(s) {sorted(unknown)}. Expected one of: {list(TIER_GROUPS)}"
                )
            chosen = []
            for group, count in tier_counts.items():
                tiers = set(TIER_GROUPS[group])
                members = [e for e in self._all.values() if e["vr_tier"] in tiers]
                if count > len(members):
                    raise ValueError(
                        f"Requested {count} from tier group {group!r} but only {len(members)} available"
                    )
                chosen.extend(rng.sample(members, count))

        else:
            raise ValueError(
                f"Unknown pool mode {mode!r}. Expected 'random', 'vr_weighted', or 'stratified'"
            )

        self._pool = {e["name"]: e for e in chosen}
        self._available = dict(self._pool)

    # ------------------------------------------------------------------
    # Live-pool mutation (picks / undo)
    # ------------------------------------------------------------------

    def available(self, sort_by: Optional[str] = None) -> list[dict]:
        entries = list(self._available.values())
        if sort_by == "tier":
            costs = self._config["tier_costs"]
            entries.sort(key=lambda e: (-costs.get(e["vr_tier"], 0), e["name"]))
        elif sort_by == "name":
            entries.sort(key=lambda e: e["name"])
        elif sort_by is not None:
            raise ValueError(f"Unknown sort_by {sort_by!r}. Expected 'tier', 'name', or None")
        return entries

    def remove(self, name: str) -> None:
        if name not in self._available:
            raise KeyError(f"{name!r} is not in the available pool")
        del self._available[name]

    def restore(self, name: str) -> None:
        if name not in self._pool:
            raise KeyError(f"{name!r} was never in the draft pool")
        self._available[name] = self._pool[name]

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[dict]:
        return self._pool.get(name)

    def tier_cost(self, vr_tier: str) -> int:
        costs: dict[str, int] = self._config["tier_costs"]
        if vr_tier not in costs:
            raise KeyError(f"Unknown tier {vr_tier!r}")
        return costs[vr_tier]
