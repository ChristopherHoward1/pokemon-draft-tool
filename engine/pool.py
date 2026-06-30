from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import yaml


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "draft_config.yaml"


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

        else:
            raise ValueError(f"Unknown pool mode {mode!r}. Expected 'random' or 'vr_weighted'")

        self._pool = {e["name"]: e for e in chosen}
        self._available = dict(self._pool)

    # ------------------------------------------------------------------
    # Live-pool mutation (picks / undo)
    # ------------------------------------------------------------------

    def available(self) -> list[dict]:
        return list(self._available.values())

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
