"""
Build the legal Pokémon pool for each draft format and emit JSON.

Usage:
    python scripts/build_pool.py aaa
    python scripts/build_pool.py pokebilities
    python scripts/build_pool.py all

Reads from:
    data/raw/            — cached Smogon HTML (produced by scrape_smogon.py)
Writes to:
    data/{format}_pokemon.json
    data/pokemon_cache/  — individual PokéAPI response cache (one file per slug)
"""

import json
import logging
import sys
import time
from pathlib import Path

import requests

# Scripts directory is on sys.path when run as:  python scripts/build_pool.py
from normalize_names import resolve, normalize
from scrape_smogon import (
    scrape_vr_thread,
    scrape_ban_spoiler,
    scrape_ban_dex,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR.parent / "data"
CACHE_DIR = DATA_DIR / "pokemon_cache"
RAW_DIR = DATA_DIR / "raw"

# ---------------------------------------------------------------------------
# Format-specific scraping config
# ---------------------------------------------------------------------------

FORMAT_CONFIG = {
    "aaa": {
        "vr_url": "https://www.smogon.com/forums/threads/aaa-viability-rankings.3770027/",
        "vr_kwargs": {"post_id": "post-9390607"},
        "ban_fn": "dex",
        "ban_url": "https://www.smogon.com/dex/sv/formats/almost-any-ability/",
        "ban_kwargs": {},
    },
    "pokebilities": {
        "vr_url": "https://www.smogon.com/forums/threads/sv-pokebilities-aaa.3751848/",
        "vr_kwargs": {"post_index": 3},
        "ban_fn": "spoiler",
        "ban_url": "https://www.smogon.com/forums/threads/sv-pokebilities-aaa.3751848/",
        "ban_kwargs": {"post_index": 0, "spoiler_label": "Banned Pokemon"},
    },
}

# SV regional dexes — union gives all obtainable species.
SV_DEX_NAMES = ["paldea", "kitakami", "blueberry"]

RATE_LIMIT_DELAY = 0.2  # seconds between PokéAPI requests


# ---------------------------------------------------------------------------
# PokéAPI helpers
# ---------------------------------------------------------------------------

def _api_get(url: str, cache_path: Path | None = None) -> dict | None:
    """Fetch JSON from PokéAPI with optional file-level caching."""
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    time.sleep(RATE_LIMIT_DELAY)
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "pokemon-draft-tool/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        log.error("API request failed for %s: %s", url, e)
        return None

    data = r.json()
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def get_sv_species() -> set[str]:
    """Return all SV-obtainable species slugs from the three regional dexes."""
    species: set[str] = set()
    for dex_name in SV_DEX_NAMES:
        cache = CACHE_DIR / f"pokedex_{dex_name}.json"
        data = _api_get(f"https://pokeapi.co/api/v2/pokedex/{dex_name}", cache)
        if not data:
            log.warning("Failed to fetch %s dex — skipping", dex_name)
            continue
        for entry in data.get("pokemon_entries", []):
            species.add(entry["pokemon_species"]["name"])
    log.info("SV obtainable species: %d", len(species))
    return species


def get_all_pokemon_slugs() -> list[str]:
    """Return every PokéAPI pokemon slug (all forms) for use as a fuzzy-match corpus."""
    cache = CACHE_DIR / "all_pokemon.json"
    data = _api_get("https://pokeapi.co/api/v2/pokemon?limit=2000", cache)
    if not data:
        return []
    names = [p["name"] for p in data.get("results", [])]
    log.info("PokéAPI pokemon list: %d entries", len(names))
    return names


def fetch_pokemon(slug: str) -> dict | None:
    """
    Fetch /pokemon/{slug} with per-slug file cache.

    Some species slugs (e.g. "toxtricity", "lycanroc") 404 on /pokemon/ because
    PokéAPI only serves form-suffixed URLs.  Fall back to /pokemon-species/{slug}
    to discover the default variety name, then fetch that instead.
    """
    cache = CACHE_DIR / f"{slug}.json"
    data = _api_get(f"https://pokeapi.co/api/v2/pokemon/{slug}", cache)
    if data is not None:
        return data

    # Species-level fallback: find the default variety and recurse once.
    species_cache = CACHE_DIR / f"species_{slug}.json"
    species = _api_get(f"https://pokeapi.co/api/v2/pokemon-species/{slug}", species_cache)
    if species is None:
        log.warning("Could not fetch PokéAPI data for %r (pokemon or species)", slug)
        return None

    default = next(
        (v["pokemon"]["name"] for v in species.get("varieties", []) if v.get("is_default")),
        None,
    )
    if default is None or default == slug:
        log.warning("No default variety found for species %r", slug)
        return None

    log.debug("Species fallback: %r → default variety %r", slug, default)
    return fetch_pokemon(default)


def pokemon_to_entry(data: dict, vr_tier: str, fmt: str) -> dict:
    """Convert raw PokéAPI pokemon data to our JSON schema."""
    dex_id = data["id"]
    name = data["name"]
    types = [t["type"]["name"] for t in data["types"]]
    bst = sum(s["base_stat"] for s in data["stats"])
    # Build a readable display name: "great-tusk" → "Great Tusk"
    display_name = " ".join(part.capitalize() for part in name.split("-"))
    return {
        "dex_id": dex_id,
        "name": name,
        "display_name": display_name,
        "types": types,
        "base_stat_total": bst,
        "vr_tier": vr_tier,
        "sprite_path": f"sprites/{dex_id}.png",
        "format": fmt,
    }


# ---------------------------------------------------------------------------
# Name resolution helpers
# ---------------------------------------------------------------------------

def resolve_names(
    names: list[str] | set[str],
    corpus: list[str],
    label: str = "name",
) -> dict[str, str]:
    """
    Resolve a collection of Smogon display names → PokéAPI slugs.

    Returns a dict {original_name: api_slug} for every name that resolves.
    Unresolved names are logged as warnings.
    """
    corpus_set = set(corpus)
    result: dict[str, str] = {}
    for name in names:
        slug = resolve(name, corpus_set)
        if slug:
            result[name] = slug
        else:
            log.warning("Unresolved %s: %r — skipping", label, name)
    return result


# ---------------------------------------------------------------------------
# Pool builder
# ---------------------------------------------------------------------------

def build_pool(fmt: str) -> list[dict]:
    """
    Build the full legal pool for one format.

    Returns a list of pokemon entry dicts matching the JSON schema.
    """
    cfg = FORMAT_CONFIG[fmt]

    # --- 1. Load VR rankings ---
    log.info("[%s] Loading VR rankings...", fmt)
    vr_entries = scrape_vr_thread(cfg["vr_url"], fmt, **cfg["vr_kwargs"])
    if not vr_entries:
        log.error("[%s] VR list is empty — aborting", fmt)
        return []

    # --- 2. Load ban list ---
    log.info("[%s] Loading ban list...", fmt)
    if cfg["ban_fn"] == "dex":
        raw_banned = scrape_ban_dex(cfg["ban_url"], fmt)
    else:
        raw_banned = scrape_ban_spoiler(cfg["ban_url"], fmt, **cfg["ban_kwargs"])

    # --- 3. Fetch SV species + full PokéAPI name list ---
    log.info("[%s] Fetching SV species list...", fmt)
    sv_species = get_sv_species()
    log.info("[%s] Fetching full PokéAPI pokemon name list...", fmt)
    all_slugs = get_all_pokemon_slugs()
    corpus = set(all_slugs)

    # --- 4. Resolve VR names → api slugs ---
    log.info("[%s] Resolving VR names...", fmt)
    vr_name_to_slug: dict[str, str] = {}
    for entry in vr_entries:
        slug = resolve(entry.name, corpus)
        if slug:
            vr_name_to_slug[entry.name] = slug
        else:
            log.warning("[%s] Unresolved VR name: %r — excluded from pool", fmt, entry.name)

    # slug → tier (last write wins if a name appears twice, which shouldn't happen)
    ranked: dict[str, str] = {slug: entry.vr_tier for entry in vr_entries
                               if (slug := vr_name_to_slug.get(entry.name))}

    # --- 5. Resolve ban names → api slugs ---
    log.info("[%s] Resolving ban list (%d names)...", fmt, len(raw_banned))
    banned_slugs: set[str] = set()
    for name in raw_banned:
        slug = resolve(name, corpus)
        if slug:
            banned_slugs.add(slug)
            # If a form was resolved (e.g. "keldeo-ordinary"), also mark the
            # base species slug as banned so it's excluded from the unranked pool
            # (the regional dex uses species names like "keldeo", not form names).
            base = slug.split("-")[0]
            if base != slug and base in sv_species:
                banned_slugs.add(base)
        else:
            log.warning("[%s] Unresolved ban name: %r — not excluded", fmt, name)

    # --- 6. Determine the full legal pool ---
    # Ranked Pokémon that aren't banned.
    legal_ranked = {slug: tier for slug, tier in ranked.items() if slug not in banned_slugs}

    # SV species that are unranked and not banned.
    # Exclude species whose slug matches a banned slug (exact) or a ranked slug.
    legal_unranked_species = [
        sp for sp in sv_species
        if sp not in banned_slugs and sp not in ranked
    ]

    log.info(
        "[%s] Legal pool: %d ranked + %d unranked species",
        fmt, len(legal_ranked), len(legal_unranked_species),
    )

    # --- 7. Fetch PokéAPI data for each entry ---
    pool: list[dict] = []
    errors: list[str] = []

    log.info("[%s] Fetching ranked Pokémon data (%d)...", fmt, len(legal_ranked))
    covered_api_slugs: set[str] = set()
    for slug, tier in sorted(legal_ranked.items()):
        data = fetch_pokemon(slug)
        if data:
            pool.append(pokemon_to_entry(data, tier, fmt))
            covered_api_slugs.add(data["name"])
        else:
            errors.append(slug)

    log.info("[%s] Fetching unranked species data (%d)...", fmt, len(legal_unranked_species))
    for species in sorted(legal_unranked_species):
        data = fetch_pokemon(species)
        if data:
            if data["name"] in covered_api_slugs:
                # Species fallback resolved to a slug already in the ranked pool
                # (e.g. "toxtricity" → "toxtricity-amped" which is already ranked C+)
                log.debug("Skipping unranked %r: already in pool as %r", species, data["name"])
                continue
            pool.append(pokemon_to_entry(data, "Unranked", fmt))
            covered_api_slugs.add(data["name"])
        else:
            errors.append(species)

    if errors:
        log.warning(
            "[%s] %d entries failed PokéAPI fetch and were excluded: %s",
            fmt, len(errors), errors[:10],
        )

    pool.sort(key=lambda e: (e["vr_tier"], e["name"]))
    log.info("[%s] Pool complete: %d Pokémon", fmt, len(pool))
    return pool


# ---------------------------------------------------------------------------
# Emit JSON
# ---------------------------------------------------------------------------

def emit_json(pool: list[dict], fmt: str) -> Path:
    out = DATA_DIR / f"{fmt}_pokemon.json"
    out.write_text(json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %d entries to %s", len(pool), out)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("aaa", "pokebilities", "all"):
        print("Usage: python scripts/build_pool.py [aaa|pokebilities|all]")
        sys.exit(1)

    formats = list(FORMAT_CONFIG.keys()) if sys.argv[1] == "all" else [sys.argv[1]]

    for fmt in formats:
        log.info("=== Building pool for %s ===", fmt)
        pool = build_pool(fmt)
        if pool:
            emit_json(pool, fmt)
        else:
            log.error("Pool for %s is empty — not writing output", fmt)


if __name__ == "__main__":
    main()
