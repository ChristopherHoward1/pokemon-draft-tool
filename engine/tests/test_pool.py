import json
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import yaml

from engine.pool import DraftPool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG = {
    "budget": 60,
    "roster_size": 10,
    "min_teams": 2,
    "max_teams": 8,
    "default_pool_size": 5,  # small for tests
    "tier_costs": {
        "S": 11, "A+": 10, "A": 9, "A-": 8,
        "B+": 7, "B": 6, "B-": 5, "C+": 4, "C": 4, "D": 3, "Unranked": 2,
    },
    "formats": {
        "aaa": "data/aaa_pokemon.json",
        "pokebilities": "data/pokebilities_pokemon.json",
    },
}

# 4 ranked + 6 unranked = 10 total, enough to exercise both modes
POKEMON = [
    {"name": "garganacl",   "display_name": "Garganacl",   "dex_id": 956, "vr_tier": "S",        "types": ["rock"],    "base_stat_total": 500, "sprite_path": "sprites/956.png",  "format": "aaa", "generation": 9},
    {"name": "dragapult",   "display_name": "Dragapult",   "dex_id": 887, "vr_tier": "A+",       "types": ["dragon", "ghost"], "base_stat_total": 600, "sprite_path": "sprites/887.png",  "format": "aaa", "generation": 9},
    {"name": "gholdengo",   "display_name": "Gholdengo",   "dex_id": 1000,"vr_tier": "A",        "types": ["steel", "ghost"],  "base_stat_total": 550, "sprite_path": "sprites/1000.png", "format": "aaa", "generation": 9},
    {"name": "skeledirge",  "display_name": "Skeledirge",  "dex_id": 911, "vr_tier": "B+",       "types": ["fire", "ghost"],   "base_stat_total": 510, "sprite_path": "sprites/911.png",  "format": "aaa", "generation": 9},
    {"name": "diglett",     "display_name": "Diglett",     "dex_id": 50,  "vr_tier": "Unranked", "types": ["ground"],  "base_stat_total": 265, "sprite_path": "sprites/50.png",   "format": "aaa", "generation": 1},
    {"name": "caterpie",    "display_name": "Caterpie",    "dex_id": 10,  "vr_tier": "Unranked", "types": ["bug"],     "base_stat_total": 195, "sprite_path": "sprites/10.png",   "format": "aaa", "generation": 1},
    {"name": "magikarp",    "display_name": "Magikarp",    "dex_id": 129, "vr_tier": "Unranked", "types": ["water"],   "base_stat_total": 200, "sprite_path": "sprites/129.png",  "format": "aaa", "generation": 1},
    {"name": "sunkern",     "display_name": "Sunkern",     "dex_id": 191, "vr_tier": "Unranked", "types": ["grass"],   "base_stat_total": 180, "sprite_path": "sprites/191.png",  "format": "aaa", "generation": 2},
    {"name": "wishiwashi",  "display_name": "Wishiwashi",  "dex_id": 746, "vr_tier": "Unranked", "types": ["water"],   "base_stat_total": 175, "sprite_path": "sprites/746.png",  "format": "aaa", "generation": 7},
    {"name": "feebas",      "display_name": "Feebas",      "dex_id": 349, "vr_tier": "Unranked", "types": ["water"],   "base_stat_total": 200, "sprite_path": "sprites/349.png",  "format": "aaa", "generation": 3},
]

CONFIG_YAML = yaml.dump(CONFIG)
POKEMON_JSON = json.dumps(POKEMON)


def make_pool(format_name: str = "aaa") -> DraftPool:
    """Return a DraftPool backed by in-memory fixtures (no disk I/O)."""
    opens = {
        str(Path(__file__).parent.parent.parent / "config" / "draft_config.yaml"): CONFIG_YAML,
        str(Path(__file__).parent.parent.parent / "data" / "aaa_pokemon.json"): POKEMON_JSON,
        str(Path(__file__).parent.parent.parent / "data" / "pokebilities_pokemon.json"): POKEMON_JSON,
    }

    def _open(path, *args, **kwargs):
        return StringIO(opens[str(path)])

    with patch("builtins.open", side_effect=_open):
        return DraftPool(format_name)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_loads_aaa_format(self):
        pool = make_pool("aaa")
        assert len(pool._all) == len(POKEMON)

    def test_loads_pokebilities_format(self):
        pool = make_pool("pokebilities")
        assert len(pool._all) == len(POKEMON)

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            make_pool("doubles")

    def test_pool_empty_before_generate(self):
        pool = make_pool()
        assert pool.available() == []


# ---------------------------------------------------------------------------
# Random mode
# ---------------------------------------------------------------------------

class TestRandomMode:
    def test_correct_size(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=42)
        assert len(pool.available()) == 5

    def test_default_size_from_config(self):
        pool = make_pool()
        pool.generate_pool(mode="random", seed=42)
        # CONFIG sets default_pool_size=5
        assert len(pool.available()) == 5

    def test_seeded_reproducible(self):
        pool1 = make_pool()
        pool1.generate_pool(mode="random", size=5, seed=99)
        pool2 = make_pool()
        pool2.generate_pool(mode="random", size=5, seed=99)
        assert [e["name"] for e in pool1.available()] == [e["name"] for e in pool2.available()]

    def test_different_seeds_differ(self):
        pool1 = make_pool()
        pool1.generate_pool(mode="random", size=5, seed=1)
        pool2 = make_pool()
        pool2.generate_pool(mode="random", size=5, seed=2)
        assert [e["name"] for e in pool1.available()] != [e["name"] for e in pool2.available()]

    def test_entries_are_from_format(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        all_names = {e["name"] for e in POKEMON}
        for entry in pool.available():
            assert entry["name"] in all_names

    def test_no_duplicates(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=10, seed=0)
        names = [e["name"] for e in pool.available()]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# VR-weighted mode
# ---------------------------------------------------------------------------

class TestVRWeightedMode:
    def test_correct_vr_and_unranked_counts(self):
        pool = make_pool()
        pool.generate_pool(mode="vr_weighted", vr_count=3, unranked_count=2, seed=0)
        ranked = [e for e in pool.available() if e["vr_tier"] != "Unranked"]
        unranked = [e for e in pool.available() if e["vr_tier"] == "Unranked"]
        assert len(ranked) == 3
        assert len(unranked) == 2

    def test_too_many_vr_raises(self):
        pool = make_pool()
        with pytest.raises(ValueError, match="VR-ranked"):
            pool.generate_pool(mode="vr_weighted", vr_count=10, unranked_count=1, seed=0)

    def test_too_many_unranked_raises(self):
        pool = make_pool()
        with pytest.raises(ValueError, match="Unranked"):
            pool.generate_pool(mode="vr_weighted", vr_count=1, unranked_count=100, seed=0)

    def test_missing_counts_raises(self):
        pool = make_pool()
        with pytest.raises(ValueError, match="vr_weighted mode requires"):
            pool.generate_pool(mode="vr_weighted", seed=0)

    def test_seeded_reproducible(self):
        pool1 = make_pool()
        pool1.generate_pool(mode="vr_weighted", vr_count=2, unranked_count=2, seed=7)
        pool2 = make_pool()
        pool2.generate_pool(mode="vr_weighted", vr_count=2, unranked_count=2, seed=7)
        assert [e["name"] for e in pool1.available()] == [e["name"] for e in pool2.available()]

    def test_unknown_mode_raises(self):
        pool = make_pool()
        with pytest.raises(ValueError, match="Unknown pool mode"):
            pool.generate_pool(mode="quota_mode", size=5, seed=0)


# ---------------------------------------------------------------------------
# Mutation: remove / restore
# ---------------------------------------------------------------------------

class TestMutation:
    def test_remove_reduces_available(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        first = pool.available()[0]["name"]
        pool.remove(first)
        names = [e["name"] for e in pool.available()]
        assert first not in names
        assert len(names) == 4

    def test_remove_not_in_pool_raises(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        with pytest.raises(KeyError):
            pool.remove("does-not-exist")

    def test_remove_already_removed_raises(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        first = pool.available()[0]["name"]
        pool.remove(first)
        with pytest.raises(KeyError):
            pool.remove(first)

    def test_restore_returns_to_available(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        first = pool.available()[0]["name"]
        pool.remove(first)
        pool.restore(first)
        names = [e["name"] for e in pool.available()]
        assert first in names
        assert len(names) == 5

    def test_restore_preserves_entry_data(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        first = pool.available()[0]
        name = first["name"]
        pool.remove(name)
        pool.restore(name)
        restored = next(e for e in pool.available() if e["name"] == name)
        assert restored == first

    def test_restore_name_not_in_pool_raises(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        with pytest.raises(KeyError):
            pool.restore("never-in-pool")


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

class TestLookups:
    def test_get_returns_entry_from_pool(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        first = pool.available()[0]["name"]
        entry = pool.get(first)
        assert entry is not None
        assert entry["name"] == first

    def test_get_picked_entry_still_returns(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        first = pool.available()[0]["name"]
        pool.remove(first)
        assert pool.get(first) is not None

    def test_get_not_in_pool_returns_none(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        assert pool.get("not-a-pokemon") is None

    def test_tier_cost_all_tiers(self):
        pool = make_pool()
        expected = {"S": 11, "A+": 10, "A": 9, "A-": 8, "B+": 7, "B": 6, "B-": 5, "C+": 4, "C": 4, "D": 3, "Unranked": 2}
        for tier, cost in expected.items():
            assert pool.tier_cost(tier) == cost

    def test_tier_cost_unknown_raises(self):
        pool = make_pool()
        with pytest.raises(KeyError):
            pool.tier_cost("Z")


# ---------------------------------------------------------------------------
# available() sort_by parameter
# ---------------------------------------------------------------------------

class TestAvailableSortBy:
    def test_sort_by_none_preserves_insertion_order(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=42)
        a = [e["name"] for e in pool.available()]
        b = [e["name"] for e in pool.available(sort_by=None)]
        assert a == b

    def test_sort_by_name_alphabetical(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        names = [e["name"] for e in pool.available(sort_by="name")]
        assert names == sorted(names)

    def test_sort_by_tier_cost_descending(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=10, seed=0)
        costs = [pool.tier_cost(e["vr_tier"]) for e in pool.available(sort_by="tier")]
        assert costs == sorted(costs, reverse=True)

    def test_sort_by_unknown_raises(self):
        pool = make_pool()
        pool.generate_pool(mode="random", size=5, seed=0)
        with pytest.raises(ValueError, match="Unknown sort_by"):
            pool.available(sort_by="cost")
