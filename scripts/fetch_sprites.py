"""
Download official-artwork sprites for every Pokémon in the pool.

Reads:
    data/aaa_pokemon.json
    data/pokebilities_pokemon.json

Writes:
    sprites/{dex_id}.png  (skipped if already present — safe to re-run)

Usage:
    python scripts/fetch_sprites.py
"""

import json
import logging
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
DATA_DIR = REPO_ROOT / "data"
SPRITES_DIR = REPO_ROOT / "sprites"

POOL_FILES = [
    DATA_DIR / "aaa_pokemon.json",
    DATA_DIR / "pokebilities_pokemon.json",
]

ARTWORK_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master"
    "/sprites/pokemon/other/official-artwork/{dex_id}.png"
)

RATE_LIMIT_DELAY = 0.15  # seconds between downloads


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_dex_ids(pool_files: list[Path]) -> list[int]:
    """Return sorted unique dex_ids from all pool JSON files."""
    ids: set[int] = set()
    for path in pool_files:
        if not path.exists():
            log.warning("Pool file not found, skipping: %s", path)
            continue
        entries = json.loads(path.read_text(encoding="utf-8"))
        for entry in entries:
            ids.add(entry["dex_id"])
    return sorted(ids)


def download_sprite(dex_id: int, sprites_dir: Path) -> bool:
    """
    Fetch the official-artwork PNG for dex_id into sprites_dir/{dex_id}.png.

    Returns True if the sprite is present after the call (downloaded or already
    existed), False if the download failed.
    Skips the network request entirely when the file already exists.
    """
    dest = sprites_dir / f"{dex_id}.png"
    if dest.exists():
        return True

    url = ARTWORK_URL.format(dex_id=dex_id)
    time.sleep(RATE_LIMIT_DELAY)
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "pokemon-draft-tool/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Sprite download failed for dex_id=%d: %s", dex_id, e)
        return False

    dest.write_bytes(r.content)
    log.debug("Saved sprite %d (%d bytes)", dex_id, len(r.content))
    return True


def fetch_all(
    dex_ids: list[int],
    sprites_dir: Path,
) -> dict[str, int]:
    """
    Download sprites for all dex_ids. Returns a summary dict with keys
    'downloaded', 'skipped', 'failed'.
    """
    sprites_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0

    for i, dex_id in enumerate(dex_ids, 1):
        dest = sprites_dir / f"{dex_id}.png"
        if dest.exists():
            skipped += 1
            continue

        ok = download_sprite(dex_id, sprites_dir)
        if ok:
            downloaded += 1
            if downloaded % 50 == 0:
                log.info(
                    "Progress: %d/%d downloaded (%d skipped, %d failed)",
                    downloaded, len(dex_ids), skipped, failed,
                )
        else:
            failed += 1

    return {"downloaded": downloaded, "skipped": skipped, "failed": failed}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    dex_ids = collect_dex_ids(POOL_FILES)
    if not dex_ids:
        log.error("No dex_ids found — run build_pool.py first")
        sys.exit(1)

    log.info("Sprites to fetch: %d unique Pokémon", len(dex_ids))
    summary = fetch_all(dex_ids, SPRITES_DIR)
    log.info(
        "Done. Downloaded: %(downloaded)d  Already present: %(skipped)d  Failed: %(failed)d",
        summary,
    )
    if summary["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
