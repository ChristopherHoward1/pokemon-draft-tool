"""
Scrapes Smogon for Viability Rankings and Ban Lists.

VR sources (forum threads — both use table format):
    python scripts/scrape_smogon.py vr   <url> <format_name> [post_index]

Ban sources (two different page types):
    python scripts/scrape_smogon.py bans-forum <url> <format_name> [post_index]
        → Pokébilities: ban list is in a bbCodeSpoiler block
    python scripts/scrape_smogon.py bans-dex   <url> <format_name>
        → AAA: ban list is in inline dexSettings JSON on the Smogon Dex page

format_name: "aaa" or "pokebilities"
Raw HTML is cached to data/raw/ — subsequent runs skip the network request.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import NamedTuple

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

# Matches tier labels as they appear in table cells, e.g.:
#   "S"  "S Rank"  "S RANK : Metagame-Defining threats"
#   "A+"  "A"  "A-"  "B+"  "B"  "B-"  "C+"  "C"  "C-"  "D"  "Unranked"
# The leading/trailing text like "Rank" and ": ..." description is stripped.
_TABLE_TIER_RE = re.compile(
    r"^\s*(?P<tier>S|A\+|A-|A|B\+|B-|B|C\+|C-|C|D|Unranked)"
    r"(?:\s+RANK|\s+Rank)?(?:\s*:.*)?$",
    re.IGNORECASE,
)

CANONICAL_TIERS = ("S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "Unranked")


class VREntry(NamedTuple):
    name: str
    vr_tier: str


# ---------------------------------------------------------------------------
# HTTP + cache helpers
# ---------------------------------------------------------------------------

def _fetch_or_load(url: str, cache_path: Path) -> str:
    if cache_path.exists():
        log.info("Using cached HTML: %s", cache_path)
        return cache_path.read_text(encoding="utf-8")
    log.info("Fetching %s", url)
    resp = requests.get(url, timeout=30, headers={"User-Agent": "pokemon-draft-tool/1.0"})
    resp.raise_for_status()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(resp.text, encoding="utf-8")
    log.info("Cached to %s", cache_path)
    return resp.text


# ---------------------------------------------------------------------------
# VR table parser
# ---------------------------------------------------------------------------

def _normalise_tier(raw: str) -> str | None:
    """Return the canonical tier string if raw matches a tier label, else None."""
    m = _TABLE_TIER_RE.match(raw.strip())
    if not m:
        return None
    t = m.group("tier")
    if t.lower() == "unranked":
        return "Unranked"
    return t.upper()


def _parse_table_vr(table: Tag) -> list[VREntry]:
    """
    Parse a Smogon VR table into (name, tier) pairs.

    Both thread formats use a table where the first column alternates between
    tier-header rows ("S Rank", "A+", "A-", …) and Pokémon-name rows.
    Blank rows are spacers and are skipped.
    """
    results: list[VREntry] = []
    current_tier: str | None = None

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        col0 = cells[0].get_text(" ", strip=True)
        if not col0:
            continue

        tier = _normalise_tier(col0)
        if tier:
            current_tier = tier
            log.debug("Tier heading: %s", tier)
            continue

        # Skip the column-header row (e.g. "Pokémon", "POKEMON : Grouped …")
        if current_tier is None:
            log.debug("Row before first tier heading, skipping: %r", col0[:60])
            continue

        results.append(VREntry(name=col0, vr_tier=current_tier))

    return results


def _find_bbwrapper(html: str, post_index: int = 0, post_id: str | None = None) -> Tag | None:
    """Return the .bbWrapper for a specific post by index or XenForo post ID."""
    soup = BeautifulSoup(html, "lxml")
    if post_id:
        article = soup.find("article", {"data-content": post_id})
        if article is None:
            log.warning("Post ID %r not found in page", post_id)
            return None
        return article.select_one(".message-body .bbWrapper")

    wrappers = soup.select(".message-body .bbWrapper")
    if post_index >= len(wrappers):
        log.warning("Post index %d out of range (only %d posts)", post_index, len(wrappers))
        return None
    return wrappers[post_index]


def scrape_vr_thread(
    url: str,
    format_name: str,
    post_index: int = 0,
    post_id: str | None = None,
) -> list[VREntry]:
    """
    Fetch (or load from cache) a Smogon forum thread and parse the VR table
    from the specified post.

    post_index: 0-based index of the post in page order (default: first post)
    post_id: XenForo post ID, e.g. "post-9390607" (overrides post_index if given)
    """
    cache_path = RAW_DIR / f"{format_name}_vr.html"
    html = _fetch_or_load(url, cache_path)

    wrapper = _find_bbwrapper(html, post_index=post_index, post_id=post_id)
    if wrapper is None:
        log.error("Cannot locate post for VR parsing")
        return []

    tables = wrapper.find_all("table")
    if not tables:
        log.warning(
            "No <table> found in VR post for %s. "
            "Thread structure may differ from expected. Inspect %s.",
            format_name, cache_path,
        )
        return []

    results = _parse_table_vr(tables[0])

    if not results:
        log.warning(
            "VR parser produced 0 entries for %s. Inspect %s.",
            format_name, cache_path,
        )
    else:
        tier_counts = {}
        for e in results:
            tier_counts[e.vr_tier] = tier_counts.get(e.vr_tier, 0) + 1
        log.info("VR parse complete for %s: %d entries across tiers: %s",
                 format_name, len(results),
                 {t: tier_counts[t] for t in CANONICAL_TIERS if t in tier_counts})
    return results


# ---------------------------------------------------------------------------
# Ban list — forum thread with bbCodeSpoiler (Pokébilities)
# ---------------------------------------------------------------------------

def _add_ban_names(banned: set, raw: str) -> None:
    """
    Add one or more Pokémon names from a raw text string to the banned set.
    Handles two multi-pokemon patterns:
      "Alolan Geodude, Graveler, and Golem"  — comma-separated with trailing "and"
      "Snorunt and Glalie"                    — " and " with no comma
    """
    parts = re.split(r",\s*", raw)
    names = []
    for part in parts:
        # Strip a leading "and " left over after comma-splitting "X, Y, and Z"
        part = re.sub(r"^\s*and\s+", "", part, flags=re.IGNORECASE).strip()
        if not part:
            continue
        # Also split "X and Y" within a single fragment (e.g. "Snorunt and Glalie")
        subparts = re.split(r"\s+and\s+", part, flags=re.IGNORECASE)
        for subpart in subparts:
            clean = subpart.strip()
            if clean:
                names.append(clean)
    if len(names) > 1:
        log.debug("Split multi-pokemon ban entry %r → %s", raw, names)
    for name in names:
        banned.add(name)

def scrape_ban_spoiler(
    url: str,
    format_name: str,
    post_index: int = 0,
    spoiler_label: str = "Banned Pokemon",
) -> set[str]:
    """
    Extract the Pokémon ban list from a Smogon thread post that uses a
    bbCodeSpoiler block (Pokébilities style).

    Each banned Pokémon appears as  <img alt=":name:"> Display Name<br/>
    inside the spoiler's .bbCodeBlock-content div.

    spoiler_label: case-insensitive substring match against the spoiler button
    text. Only the matching spoiler is parsed. Pokébilities uses "Banned Pokemon".
    """
    cache_path = RAW_DIR / f"{format_name}_bans.html"
    html = _fetch_or_load(url, cache_path)

    wrapper = _find_bbwrapper(html, post_index=post_index)
    if wrapper is None:
        log.error("Cannot locate post for ban-spoiler parsing")
        return set()

    all_spoilers = wrapper.find_all(class_="bbCodeSpoiler")
    if not all_spoilers:
        log.warning(
            "No bbCodeSpoiler blocks found in post %d for %s. Inspect %s.",
            post_index, format_name, cache_path,
        )
        return set()

    # Filter to the spoiler whose button text matches the label.
    label_lower = spoiler_label.lower()
    spoilers = [
        sp for sp in all_spoilers
        if (btn := sp.find("button")) and label_lower in btn.get_text(strip=True).lower()
    ]
    if not spoilers:
        log.warning(
            "No spoiler matching %r found in post %d for %s (found: %s). "
            "Inspect %s.",
            spoiler_label, post_index, format_name,
            [sp.find("button").get_text(strip=True) for sp in all_spoilers if sp.find("button")],
            cache_path,
        )
        return set()

    log.debug("Found %d matching spoiler(s) for label %r", len(spoilers), spoiler_label)

    banned: set[str] = set()
    for spoiler in spoilers:
        content = spoiler.select_one(".bbCodeBlock-content")
        if content is None:
            continue

        # Each entry: <img alt=":slug:"> Name<br/>
        # Some entries list multiple Pokémon after one sprite:
        #   "Alolan Geodude, Graveler, and Golem"
        # Split those into individual names.
        for img in content.find_all("img", class_="smilie"):
            sibling = img.next_sibling
            if isinstance(sibling, NavigableString):
                raw = str(sibling).strip()
                if raw:
                    _add_ban_names(banned, raw)
                    continue
            # Fallback: derive from alt attr ":slug:" → slug text
            alt = img.get("alt", "")
            if alt.startswith(":") and alt.endswith(":"):
                slug = alt[1:-1]
                name = slug.replace("-", " ").title()
                log.debug("Ban name from alt slug (fallback): %r → %r", slug, name)
                banned.add(name)

    if not banned:
        log.warning(
            "Ban-spoiler parser found 0 entries for %s. Inspect %s.",
            format_name, cache_path,
        )
    else:
        log.info("Ban-spoiler parse complete for %s: %d entries", format_name, len(banned))

    return banned


# ---------------------------------------------------------------------------
# Ban list — Smogon Dex page with inline dexSettings JSON (AAA)
# ---------------------------------------------------------------------------

def _extract_dexsettings(html: str) -> dict | None:
    """Extract and parse the dexSettings JSON object embedded in the page."""
    m = re.search(r"dexSettings\s*=\s*(\{.+)", html, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    depth = 0
    for i, c in enumerate(raw):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                raw = raw[: i + 1]
                break
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("Failed to parse dexSettings JSON: %s", e)
        return None


def scrape_ban_dex(url: str, format_name: str) -> set[str]:
    """
    Extract the Pokémon ban list from a Smogon Dex format page.

    The page embeds a dexSettings JSON blob. The relevant data is in
    injectRpcs[dump-format].description — an HTML string with a
    <h3>Pokémon Restrictions</h3> section followed by <li> entries.
    """
    cache_path = RAW_DIR / f"{format_name}_bans_dex.html"
    html = _fetch_or_load(url, cache_path)

    data = _extract_dexsettings(html)
    if data is None:
        log.error("No dexSettings found in %s", url)
        return set()

    description_html: str | None = None
    for rpc in data.get("injectRpcs", []):
        name, payload = rpc[0], rpc[1]
        if "dump-format" in name and isinstance(payload, dict):
            description_html = payload.get("description", "")
            break

    if not description_html:
        log.warning("No dump-format description found in dexSettings for %s", format_name)
        return set()

    soup = BeautifulSoup(description_html, "lxml")
    banned: set[str] = set()
    in_restrictions = False

    for tag in soup.find_all(["h3", "li"]):
        if tag.name == "h3":
            in_restrictions = "Pokémon Restrictions" in tag.get_text()
            continue
        if tag.name == "li" and in_restrictions:
            name = tag.get_text(strip=True)
            if name:
                banned.add(name)

    if not banned:
        log.warning(
            "Ban-dex parser found 0 entries for %s. Inspect %s.",
            format_name, cache_path,
        )
    else:
        log.info("Ban-dex parse complete for %s: %d entries", format_name, len(banned))

    return banned


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    usage = __doc__
    if len(sys.argv) < 4:
        print(usage)
        sys.exit(1)

    command = sys.argv[1]
    url = sys.argv[2]
    format_name = sys.argv[3]

    if command == "vr":
        post_index = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        entries = scrape_vr_thread(url, format_name, post_index=post_index)
        for e in entries:
            print(f"{e.vr_tier}\t{e.name}")

    elif command == "bans-forum":
        post_index = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        banned = scrape_ban_spoiler(url, format_name, post_index=post_index)
        for name in sorted(banned):
            print(name)

    elif command == "bans-dex":
        banned = scrape_ban_dex(url, format_name)
        for name in sorted(banned):
            print(name)

    else:
        print(f"Unknown command: {command!r}. Use 'vr', 'bans-forum', or 'bans-dex'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
