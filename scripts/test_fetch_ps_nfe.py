"""
Tests for fetch_ps_nfe.py.

All HTTP calls are mocked; cache behaviour is tested with tempfile paths.
Run with: python -m pytest scripts/test_fetch_ps_nfe.py -v
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import fetch_ps_nfe as m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_POKEDEX = {
    "haunter":    {"num": 93,  "name": "Haunter",   "nfe": True},
    "gengar":     {"num": 94,  "name": "Gengar"},
    "chansey":    {"num": 113, "name": "Chansey",   "nfe": True},
    "blissey":    {"num": 242, "name": "Blissey"},
    "eevee":      {"num": 133, "name": "Eevee",     "nfe": True},
    "espeon":     {"num": 196, "name": "Espeon"},
    "greattusk":  {"num": 997, "name": "Great Tusk"},
}

_SAMPLE_NFE = {"haunter", "chansey", "eevee"}

_PS_JS = f"exports.BattlePokedex = {json.dumps(_SAMPLE_POKEDEX)};"


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.text = text
    r.raise_for_status = lambda: None
    return r


# ---------------------------------------------------------------------------
# fetch_ps_nfe_set — parsing
# ---------------------------------------------------------------------------

def test_fetch_ps_nfe_set_parses_exports_form(tmp_path):
    with patch.object(m, "_CACHE_FILE", tmp_path / "ps_pokedex.json"):
        with patch("requests.get", return_value=_make_response(_PS_JS)):
            result = m.fetch_ps_nfe_set()
    assert result == _SAMPLE_NFE


def test_fetch_ps_nfe_set_parses_var_form(tmp_path):
    js = f"var BattlePokedex = {json.dumps(_SAMPLE_POKEDEX)};"
    with patch.object(m, "_CACHE_FILE", tmp_path / "ps_pokedex.json"):
        with patch("requests.get", return_value=_make_response(js)):
            result = m.fetch_ps_nfe_set()
    assert result == _SAMPLE_NFE


def test_fetch_ps_nfe_set_populates_all_slugs(tmp_path):
    with patch.object(m, "_CACHE_FILE", tmp_path / "ps_pokedex.json"):
        with patch("requests.get", return_value=_make_response(_PS_JS)):
            m.fetch_ps_nfe_set()
    assert m._PS_ALL_SLUGS == set(_SAMPLE_POKEDEX.keys())


def test_fetch_ps_nfe_set_writes_cache(tmp_path):
    cache = tmp_path / "ps_pokedex.json"
    with patch.object(m, "_CACHE_FILE", cache):
        with patch("requests.get", return_value=_make_response(_PS_JS)):
            m.fetch_ps_nfe_set()
    assert cache.exists()
    stored = json.loads(cache.read_text())
    assert stored == _SAMPLE_POKEDEX


# ---------------------------------------------------------------------------
# fetch_ps_nfe_set — cache behaviour
# ---------------------------------------------------------------------------

def test_fetch_ps_nfe_set_uses_fresh_cache(tmp_path):
    cache = tmp_path / "ps_pokedex.json"
    cache.write_text(json.dumps(_SAMPLE_POKEDEX), encoding="utf-8")
    # mtime is now → fresh
    with patch.object(m, "_CACHE_FILE", cache):
        with patch("requests.get") as mock_get:
            result = m.fetch_ps_nfe_set()
            mock_get.assert_not_called()
    assert result == _SAMPLE_NFE


def test_fetch_ps_nfe_set_refetches_stale_cache(tmp_path):
    cache = tmp_path / "ps_pokedex.json"
    cache.write_text(json.dumps(_SAMPLE_POKEDEX), encoding="utf-8")
    old = time.time() - 8 * 86400
    os.utime(cache, (old, old))
    with patch.object(m, "_CACHE_FILE", cache):
        with patch("requests.get", return_value=_make_response(_PS_JS)) as mock_get:
            result = m.fetch_ps_nfe_set()
            mock_get.assert_called_once()
    assert result == _SAMPLE_NFE


def test_fetch_ps_nfe_set_refetches_corrupt_cache(tmp_path):
    cache = tmp_path / "ps_pokedex.json"
    cache.write_text("not json", encoding="utf-8")
    with patch.object(m, "_CACHE_FILE", cache):
        with patch("requests.get", return_value=_make_response(_PS_JS)) as mock_get:
            result = m.fetch_ps_nfe_set()
            mock_get.assert_called_once()
    assert result == _SAMPLE_NFE


# ---------------------------------------------------------------------------
# fetch_ps_nfe_set — network failure
# ---------------------------------------------------------------------------

def test_fetch_ps_nfe_set_returns_empty_on_http_error(tmp_path):
    import requests as req
    with patch.object(m, "_CACHE_FILE", tmp_path / "ps_pokedex.json"):
        with patch("requests.get", side_effect=req.RequestException("timeout")):
            result = m.fetch_ps_nfe_set()
    assert result == set()


def test_fetch_ps_nfe_set_returns_empty_on_bad_js_format(tmp_path):
    with patch.object(m, "_CACHE_FILE", tmp_path / "ps_pokedex.json"):
        with patch("requests.get", return_value=_make_response("window.foo = {};")):
            result = m.fetch_ps_nfe_set()
    assert result == set()


# ---------------------------------------------------------------------------
# is_fully_evolved_ps
# ---------------------------------------------------------------------------

def test_is_fully_evolved_nfe_slug_returns_false():
    assert m.is_fully_evolved_ps("haunter", {"haunter"}) is False


def test_is_fully_evolved_not_in_nfe_set_returns_true():
    assert m.is_fully_evolved_ps("gengar", {"haunter"}) is True


def test_is_fully_evolved_empty_nfe_set_returns_true():
    assert m.is_fully_evolved_ps("gengar", set()) is True


def test_is_fully_evolved_normalizes_hyphen_slug():
    # "great-tusk" → "greattusk"; if "greattusk" is in nfe_set → NFE
    assert m.is_fully_evolved_ps("great-tusk", {"greattusk"}) is False
    # not in nfe_set → fully evolved
    assert m.is_fully_evolved_ps("great-tusk", set()) is True


def test_is_fully_evolved_miss_logs_warning(caplog):
    prev = m._PS_ALL_SLUGS
    m._PS_ALL_SLUGS = {"haunter", "gengar"}
    try:
        with caplog.at_level(logging.WARNING, logger="fetch_ps_nfe"):
            result = m.is_fully_evolved_ps("unknownmon", set())
        assert result is True
        assert any("NFE lookup miss" in r.message for r in caplog.records)
    finally:
        m._PS_ALL_SLUGS = prev


def test_is_fully_evolved_known_slug_no_miss_log(caplog):
    prev = m._PS_ALL_SLUGS
    m._PS_ALL_SLUGS = {"haunter", "gengar"}
    try:
        with caplog.at_level(logging.WARNING, logger="fetch_ps_nfe"):
            m.is_fully_evolved_ps("gengar", set())
        assert not any("NFE lookup miss" in r.message for r in caplog.records)
    finally:
        m._PS_ALL_SLUGS = prev


# ---------------------------------------------------------------------------
# Spot checks matching spec acceptance criteria
# ---------------------------------------------------------------------------

def test_spot_checks_via_nfe_set():
    nfe_set = {"haunter", "eevee", "chansey"}
    assert m.is_fully_evolved_ps("haunter", nfe_set) is False   # absent
    assert m.is_fully_evolved_ps("gengar", nfe_set) is True     # present
    assert m.is_fully_evolved_ps("eevee", nfe_set) is False     # absent
    assert m.is_fully_evolved_ps("espeon", nfe_set) is True     # present
    # chansey excluded by filter; EVIOLITE_EXCEPTIONS handled at build_pool layer
    assert m.is_fully_evolved_ps("chansey", nfe_set) is False


# ---------------------------------------------------------------------------
# EVIOLITE_EXCEPTIONS constant
# ---------------------------------------------------------------------------

def test_eviolite_exceptions_contents():
    assert "chansey" in m.EVIOLITE_EXCEPTIONS
    assert "dusclops" in m.EVIOLITE_EXCEPTIONS
    assert "porygon2" in m.EVIOLITE_EXCEPTIONS
    assert "vigoroth" in m.EVIOLITE_EXCEPTIONS
    assert "gligar" in m.EVIOLITE_EXCEPTIONS
