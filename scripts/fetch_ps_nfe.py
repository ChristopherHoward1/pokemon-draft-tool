"""
Pokémon Showdown NFE (not-fully-evolved) lookup.

Fetches Pokémon Showdown's static pokedex and extracts the set of slugs that
can still evolve — one fetch, one parse, one dict lookup per Pokémon; no
per-species API calls, no evolution chain walking.

Note on the data signal: Pokémon Showdown's client data files do NOT carry an
explicit ``nfe`` flag (PS computes that at runtime in the battle simulator).
The reliable static signal is the ``evos`` field: a species is not fully
evolved iff it has a non-empty ``evos`` list. We fetch pokedex.json (valid
JSON) rather than pokedex.js (a JS object literal with unquoted keys that the
stdlib json parser cannot read).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

_PS_POKEDEX_URL = "https://play.pokemonshowdown.com/data/pokedex.json"
_CACHE_FILE = Path(__file__).parent.parent / "data" / "pokemon_cache" / "ps_pokedex.json"
_CACHE_MAX_AGE_DAYS = 7

# Pre-evolutions explicitly kept in the draft pool because they are competitively
# viable via Eviolite and stronger in practice than their final forms.
EVIOLITE_EXCEPTIONS: frozenset[str] = frozenset({
    "chansey",
    "dusclops",
    "gligar",
    "porygon2",
    "vigoroth",
})

# Populated by fetch_ps_nfe_set(); used by is_fully_evolved_ps() to distinguish
# "fully evolved" from "not in PS dex at all" (miss detection).
_PS_ALL_SLUGS: set[str] = set()


def _api_slug_to_ps_slug(api_slug: str) -> str:
    """Convert a PokéAPI slug (hyphen-separated) to a PS slug (lowercase, no hyphens)."""
    return api_slug.replace("-", "").lower()


def _nfe_slugs(data: dict) -> set[str]:
    """Return the set of slugs that are not fully evolved (have a non-empty ``evos``)."""
    return {slug for slug, entry in data.items() if entry.get("evos")}


def fetch_ps_nfe_set() -> set[str]:
    """
    Return the set of PS slugs that are not fully evolved.

    Fetches Pokémon Showdown's pokedex.json, parses it, derives the NFE set from
    the ``evos`` field, and caches the parsed dex to
    data/pokemon_cache/ps_pokedex.json for up to 7 days.
    """
    global _PS_ALL_SLUGS

    if _CACHE_FILE.exists():
        age_days = (time.time() - _CACHE_FILE.stat().st_mtime) / 86400
        if age_days < _CACHE_MAX_AGE_DAYS:
            try:
                data: dict = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                _PS_ALL_SLUGS = set(data.keys())
                nfe_set = _nfe_slugs(data)
                log.info("PS pokedex loaded from cache (%d NFE entries)", len(nfe_set))
                return nfe_set
            except (json.JSONDecodeError, OSError):
                log.warning("PS pokedex cache is corrupt — re-fetching")

    log.info("Fetching PS pokedex from %s", _PS_POKEDEX_URL)
    try:
        r = requests.get(_PS_POKEDEX_URL, timeout=30, headers={"User-Agent": "pokemon-draft-tool/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        log.error("Failed to fetch PS pokedex: %s — NFE filter disabled", e)
        return set()

    try:
        data = json.loads(r.text)
    except json.JSONDecodeError as e:
        log.error("PS pokedex JSON parse failed: %s — NFE filter disabled", e)
        return set()

    if not isinstance(data, dict) or not data:
        log.error("PS pokedex has unexpected shape — NFE filter disabled")
        return set()

    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    _PS_ALL_SLUGS = set(data.keys())
    nfe_set = _nfe_slugs(data)
    log.info("PS pokedex fetched and cached: %d entries, %d NFE", len(data), len(nfe_set))
    return nfe_set


def is_fully_evolved_ps(api_slug: str, nfe_set: set[str]) -> bool:
    """
    Return True if the Pokémon is fully evolved (or standalone).

    Converts the PokéAPI slug to a PS slug before checking. Logs a warning for
    any slug that is absent from the PS dex entirely — these are treated
    conservatively as fully evolved.
    """
    ps_slug = _api_slug_to_ps_slug(api_slug)
    if ps_slug in nfe_set:
        return False
    if _PS_ALL_SLUGS and ps_slug not in _PS_ALL_SLUGS:
        log.warning("NFE lookup miss, treating as fully evolved: %s", api_slug)
    return True
