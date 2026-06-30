"""
Tests for build_pool.py.

All PokéAPI and Smogon network calls are mocked so the suite runs offline.
Run with: python -m pytest scripts/test_build_pool.py -v
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import pytest

import build_pool as m
from scrape_smogon import VREntry


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _poke_data(name: str, dex_id: int = 1, types: list[str] | None = None, bst: int = 300) -> dict:
    """Minimal PokéAPI /pokemon/{name} payload."""
    types = types or ["normal"]
    return {
        "id": dex_id,
        "name": name,
        "types": [{"type": {"name": t}} for t in types],
        "stats": [{"base_stat": bst // 6}] * 6,  # approximate
    }


SAMPLE_SV_SPECIES = {"corviknight", "great-tusk", "gholdengo", "talonflame", "blissey", "smeargle"}
SAMPLE_ALL_SLUGS = list(SAMPLE_SV_SPECIES) + [
    "ogerpon-wellspring-mask", "landorus-incarnate", "landorus-therian",
    "flutter-mane",
]

SAMPLE_VR_ENTRIES = [
    VREntry("Corviknight", "A+"),
    VREntry("Great Tusk", "A+"),
    VREntry("Gholdengo", "A"),
    VREntry("Talonflame", "C"),
]

SAMPLE_BANNED = {"Flutter Mane", "Smeargle"}

SAMPLE_POKE_DATA = {
    "corviknight":  _poke_data("corviknight", 879, ["steel", "flying"], 600),
    "great-tusk":   _poke_data("great-tusk", 997, ["ground", "fighting"], 570),
    "gholdengo":    _poke_data("gholdengo", 1000, ["steel", "ghost"], 550),
    "talonflame":   _poke_data("talonflame", 663, ["fire", "flying"], 499),
    "blissey":      _poke_data("blissey", 242, ["normal"], 540),
    "smeargle":     _poke_data("smeargle", 235, ["normal"], 250),
    "flutter-mane": _poke_data("flutter-mane", 987, ["ghost", "fairy"], 570),
}


def _make_fetch_pokemon(data_map: dict):
    """Return a mock for fetch_pokemon that reads from data_map."""
    def _fetch(slug):
        return data_map.get(slug)
    return _fetch


# ---------------------------------------------------------------------------
# pokemon_to_entry
# ---------------------------------------------------------------------------

def test_pokemon_to_entry_fields():
    data = _poke_data("great-tusk", 997, ["ground", "fighting"], 570)
    entry = m.pokemon_to_entry(data, "A+", "aaa")
    assert entry["dex_id"] == 997
    assert entry["name"] == "great-tusk"
    assert entry["display_name"] == "Great Tusk"
    assert set(entry["types"]) == {"ground", "fighting"}
    assert entry["vr_tier"] == "A+"
    assert entry["format"] == "aaa"
    assert entry["sprite_path"] == "sprites/997.png"
    assert isinstance(entry["base_stat_total"], int)


def test_pokemon_to_entry_bst():
    # 6 stats each = 50, total should be 300
    data = _poke_data("blissey", 242, ["normal"], 300)
    entry = m.pokemon_to_entry(data, "Unranked", "aaa")
    assert entry["base_stat_total"] == 300


def test_pokemon_to_entry_display_name_hyphenated():
    data = _poke_data("landorus-therian", 645, ["ground", "flying"], 600)
    entry = m.pokemon_to_entry(data, "A-", "aaa")
    assert entry["display_name"] == "Landorus Therian"


# ---------------------------------------------------------------------------
# resolve_names
# ---------------------------------------------------------------------------

def test_resolve_names_all_known():
    corpus = ["corviknight", "great-tusk", "gholdengo"]
    result = m.resolve_names(["Corviknight", "Great Tusk", "Gholdengo"], corpus)
    assert result == {"Corviknight": "corviknight", "Great Tusk": "great-tusk", "Gholdengo": "gholdengo"}


def test_resolve_names_unresolved_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="build_pool"):
        result = m.resolve_names(["Totally Unknown Mon"], ["corviknight"])
    assert "Totally Unknown Mon" not in result
    assert any("Unresolved" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# build_pool (fully mocked)
# ---------------------------------------------------------------------------

def _patch_scraping(vr_entries, banned):
    """Context manager patches for scrape_* and API calls."""
    return [
        patch("build_pool.scrape_vr_thread", return_value=vr_entries),
        patch("build_pool.scrape_ban_dex", return_value=banned),
        patch("build_pool.scrape_ban_spoiler", return_value=banned),
        patch("build_pool.get_sv_species", return_value=SAMPLE_SV_SPECIES),
        patch("build_pool.get_all_pokemon_slugs", return_value=SAMPLE_ALL_SLUGS),
        patch("build_pool.fetch_pokemon", side_effect=_make_fetch_pokemon(SAMPLE_POKE_DATA)),
    ]


def _run_build_pool(fmt: str, vr_entries=None, banned=None):
    if vr_entries is None:
        vr_entries = SAMPLE_VR_ENTRIES
    if banned is None:
        banned = SAMPLE_BANNED
    patches = _patch_scraping(vr_entries, banned)
    ctx = [p.__enter__() for p in patches]
    try:
        return m.build_pool(fmt)
    finally:
        for p, c in zip(patches, ctx):
            p.__exit__(None, None, None)


def test_build_pool_returns_list():
    pool = _run_build_pool("aaa")
    assert isinstance(pool, list)
    assert len(pool) > 0


def test_build_pool_ranked_tiers_preserved():
    pool = _run_build_pool("aaa")
    by_name = {e["name"]: e for e in pool}
    assert by_name["corviknight"]["vr_tier"] == "A+"
    assert by_name["great-tusk"]["vr_tier"] == "A+"
    assert by_name["gholdengo"]["vr_tier"] == "A"
    assert by_name["talonflame"]["vr_tier"] == "C"


def test_build_pool_banned_excluded():
    # flutter-mane is in SAMPLE_ALL_SLUGS but listed in SAMPLE_BANNED
    pool = _run_build_pool("aaa")
    names = {e["name"] for e in pool}
    assert "flutter-mane" not in names
    # smeargle is banned; it's also in sv_species
    assert "smeargle" not in names


def test_build_pool_unranked_legal_species_included():
    # blissey is in sv_species but not in vr_entries and not banned
    pool = _run_build_pool("aaa")
    by_name = {e["name"]: e for e in pool}
    assert "blissey" in by_name
    assert by_name["blissey"]["vr_tier"] == "Unranked"


def test_build_pool_schema_fields():
    pool = _run_build_pool("aaa")
    required = {"dex_id", "name", "display_name", "types", "base_stat_total", "vr_tier", "sprite_path", "format"}
    for entry in pool:
        missing = required - entry.keys()
        assert missing == set(), f"Missing fields in {entry['name']!r}: {missing}"


def test_build_pool_types_are_list():
    pool = _run_build_pool("aaa")
    for entry in pool:
        assert isinstance(entry["types"], list)
        assert all(isinstance(t, str) for t in entry["types"])


def test_build_pool_empty_vr_returns_empty(caplog):
    with caplog.at_level(logging.ERROR, logger="build_pool"):
        pool = _run_build_pool("aaa", vr_entries=[])
    assert pool == []


def test_build_pool_pokebilities_format():
    pool = _run_build_pool("pokebilities")
    assert all(e["format"] == "pokebilities" for e in pool)


# ---------------------------------------------------------------------------
# emit_json
# ---------------------------------------------------------------------------

def test_emit_json_writes_valid_file():
    pool = [
        {"dex_id": 879, "name": "corviknight", "display_name": "Corviknight",
         "types": ["steel", "flying"], "base_stat_total": 600,
         "vr_tier": "A+", "sprite_path": "sprites/879.png", "format": "aaa"},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.DATA_DIR
        m.DATA_DIR = Path(tmpdir)
        try:
            out = m.emit_json(pool, "aaa")
            assert out.exists()
            loaded = json.loads(out.read_text())
            assert loaded == pool
        finally:
            m.DATA_DIR = orig


# ---------------------------------------------------------------------------
# get_sv_species (mocked HTTP)
# ---------------------------------------------------------------------------

def _make_dex_response(names: list[str]) -> dict:
    return {"pokemon_entries": [{"pokemon_species": {"name": n}} for n in names]}


def test_get_sv_species_unions_three_dexes():
    responses = {
        "https://pokeapi.co/api/v2/pokedex/paldea":    _make_dex_response(["sprigatito", "fuecoco"]),
        "https://pokeapi.co/api/v2/pokedex/kitakami":  _make_dex_response(["fuecoco", "okidogi"]),
        "https://pokeapi.co/api/v2/pokedex/blueberry": _make_dex_response(["doduo", "sprigatito"]),
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_cache = m.CACHE_DIR
        m.CACHE_DIR = Path(tmpdir)
        with patch("build_pool._api_get", side_effect=lambda url, *a, **kw: responses.get(url)):
            species = m.get_sv_species()
        m.CACHE_DIR = orig_cache

    assert species == {"sprigatito", "fuecoco", "okidogi", "doduo"}


def test_get_sv_species_deduplicates():
    all_same = _make_dex_response(["pikachu", "pikachu", "raichu"])
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_cache = m.CACHE_DIR
        m.CACHE_DIR = Path(tmpdir)
        with patch("build_pool._api_get", return_value=all_same):
            species = m.get_sv_species()
        m.CACHE_DIR = orig_cache

    assert "pikachu" in species
    assert isinstance(species, set)
