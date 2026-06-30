import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from engine.pool import DraftPool
from engine.validator import PickResult, Validator

# ---------------------------------------------------------------------------
# Shared fixtures (same shape as test_pool.py)
# ---------------------------------------------------------------------------

CONFIG = {
    "budget": 60,
    "roster_size": 3,  # small to make roster-full tests easy
    "min_teams": 2,
    "max_teams": 8,
    "default_pool_size": 4,
    "tier_costs": {
        "S": 11, "A+": 10, "A": 9, "A-": 8,
        "B+": 7, "B": 6, "B-": 5, "C": 4, "D": 3, "Unranked": 2,
    },
    "formats": {
        "aaa": "data/aaa_pokemon.json",
        "pokebilities": "data/pokebilities_pokemon.json",
    },
}

# garganacl: S (cost 11), magikarp: Unranked (cost 2)
POKEMON = [
    {"name": "garganacl",  "display_name": "Garganacl",  "dex_id": 956, "vr_tier": "S",        "types": ["rock"],  "base_stat_total": 500, "sprite_path": "sprites/956.png",  "format": "aaa", "generation": 9},
    {"name": "dragapult",  "display_name": "Dragapult",  "dex_id": 887, "vr_tier": "A+",       "types": ["dragon", "ghost"], "base_stat_total": 600, "sprite_path": "sprites/887.png",  "format": "aaa", "generation": 9},
    {"name": "gholdengo",  "display_name": "Gholdengo",  "dex_id": 1000,"vr_tier": "A",        "types": ["steel", "ghost"],  "base_stat_total": 550, "sprite_path": "sprites/1000.png", "format": "aaa", "generation": 9},
    {"name": "magikarp",   "display_name": "Magikarp",   "dex_id": 129, "vr_tier": "Unranked", "types": ["water"], "base_stat_total": 200, "sprite_path": "sprites/129.png",  "format": "aaa", "generation": 1},
]

CONFIG_YAML = yaml.dump(CONFIG)
POKEMON_JSON = json.dumps(POKEMON)


def make_validator() -> tuple[DraftPool, Validator]:
    opens = {
        str(Path(__file__).parent.parent.parent / "config" / "draft_config.yaml"): CONFIG_YAML,
        str(Path(__file__).parent.parent.parent / "data" / "aaa_pokemon.json"): POKEMON_JSON,
    }

    def _open(path, *args, **kwargs):
        return StringIO(opens[str(path)])

    with patch("builtins.open", side_effect=_open):
        pool = DraftPool("aaa")

    pool.generate_pool(mode="random", size=4, seed=0)
    v = Validator(pool)
    return pool, v


# ---------------------------------------------------------------------------
# PickResult dataclass
# ---------------------------------------------------------------------------

class TestPickResult:
    def test_valid_result(self):
        r = PickResult(valid=True)
        assert r.valid is True
        assert r.reason == ""

    def test_invalid_result_with_reason(self):
        r = PickResult(valid=False, reason="something went wrong")
        assert r.valid is False
        assert r.reason == "something went wrong"

    def test_frozen(self):
        r = PickResult(valid=True)
        with pytest.raises((AttributeError, TypeError)):
            r.valid = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Valid pick
# ---------------------------------------------------------------------------

class TestValidPick:
    def test_valid_pick_returns_true(self):
        pool, v = make_validator()
        name = pool.available()[0]["name"]
        result = v.check(name, remaining_budget=60, picks_made=0)
        assert result.valid is True
        assert result.reason == ""

    def test_budget_exactly_equal_to_cost_is_valid(self):
        pool, v = make_validator()
        # magikarp costs 2 — pick with exactly 2 remaining
        result = v.check("magikarp", remaining_budget=2, picks_made=0)
        assert result.valid is True

    def test_last_roster_slot_is_valid(self):
        pool, v = make_validator()
        # roster_size=3, picks_made=2 → one slot left
        result = v.check("magikarp", remaining_budget=60, picks_made=2)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Check 1: not in available pool
# ---------------------------------------------------------------------------

class TestNotInPool:
    def test_unknown_name_fails(self):
        _, v = make_validator()
        result = v.check("pikachu", remaining_budget=60, picks_made=0)
        assert result.valid is False
        assert "not in the available pool" in result.reason
        assert "pikachu" in result.reason

    def test_already_picked_fails(self):
        pool, v = make_validator()
        name = pool.available()[0]["name"]
        pool.remove(name)
        result = v.check(name, remaining_budget=60, picks_made=0)
        assert result.valid is False
        assert "not in the available pool" in result.reason

    def test_pool_check_before_roster_check(self):
        # Unavailable AND roster full → pool error wins
        pool, v = make_validator()
        name = pool.available()[0]["name"]
        pool.remove(name)
        result = v.check(name, remaining_budget=60, picks_made=3)
        assert "not in the available pool" in result.reason

    def test_pool_check_before_budget_check(self):
        # Unavailable AND no budget → pool error wins
        pool, v = make_validator()
        name = pool.available()[0]["name"]
        pool.remove(name)
        result = v.check(name, remaining_budget=0, picks_made=0)
        assert "not in the available pool" in result.reason


# ---------------------------------------------------------------------------
# Check 2: roster full
# ---------------------------------------------------------------------------

class TestRosterFull:
    def test_roster_full_fails(self):
        pool, v = make_validator()
        result = v.check("magikarp", remaining_budget=60, picks_made=3)
        assert result.valid is False
        assert "roster is full" in result.reason
        assert "3/3" in result.reason

    def test_roster_check_before_budget_check(self):
        # Roster full AND no budget → roster error wins
        pool, v = make_validator()
        result = v.check("magikarp", remaining_budget=0, picks_made=3)
        assert "roster is full" in result.reason


# ---------------------------------------------------------------------------
# Check 3: insufficient budget
# ---------------------------------------------------------------------------

class TestInsufficientBudget:
    def test_zero_budget_fails(self):
        pool, v = make_validator()
        result = v.check("magikarp", remaining_budget=0, picks_made=0)
        assert result.valid is False
        assert "insufficient budget" in result.reason

    def test_one_below_cost_fails(self):
        pool, v = make_validator()
        # garganacl costs 11; 10 is one short
        result = v.check("garganacl", remaining_budget=10, picks_made=0)
        assert result.valid is False
        assert "insufficient budget" in result.reason
        assert "11" in result.reason   # cost
        assert "10" in result.reason   # remaining

    def test_reason_includes_name_and_cost(self):
        pool, v = make_validator()
        result = v.check("garganacl", remaining_budget=5, picks_made=0)
        assert "garganacl" in result.reason
        assert "11" in result.reason
        assert "5" in result.reason
