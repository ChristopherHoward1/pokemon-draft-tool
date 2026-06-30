"""
Name normalization for mapping Smogon display names → PokéAPI slugs.

PokéAPI slugs are lowercase, hyphen-separated, ASCII (e.g. "great-tusk",
"landorus-therian", "geodude-alola").  Smogon names differ in predictable ways
that this module corrects.

Usage:
    from normalize_names import normalize, resolve

    slug = normalize("Great Tusk")          # → "great-tusk"
    slug = normalize("Ogerpon-Wellspring")  # → "ogerpon-wellspring-mask"

    # resolve also does a fuzzy-match fallback against a known API name list
    slug = resolve("Ogerpon-Cornerstone", api_name_set)
"""

import logging
import re
import unicodedata
from collections.abc import Collection

from rapidfuzz import process as fz_process, fuzz

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exception table
# ---------------------------------------------------------------------------
# Keys: the output of _basic_slug() applied to a Smogon display name.
# Values: the correct PokéAPI slug.
#
# Add entries here as new mismatches are discovered during pipeline runs.
# The comment on each entry explains WHY the exception exists.

KNOWN_EXCEPTIONS: dict[str, str] = {
    # Smogon uses "-I" as shorthand for Incarnate (Therian is spelled out in full).
    "landorus-i": "landorus-incarnate",
    "tornadus-i": "tornadus-incarnate",
    "thundurus-i": "thundurus-incarnate",
    "enamorus-i": "enamorus-incarnate",

    # Smogon omits the "-mask" suffix on Ogerpon's forms.
    "ogerpon-wellspring": "ogerpon-wellspring-mask",
    "ogerpon-hearthflame": "ogerpon-hearthflame-mask",
    "ogerpon-cornerstone": "ogerpon-cornerstone-mask",

    # PokéAPI uses the "alola" suffix; Smogon prefixes with "Alolan ".
    "alolan-geodude": "geodude-alola",
    "alolan-graveler": "graveler-alola",
    "alolan-golem": "golem-alola",
    "alolan-ninetales": "ninetales-alola",
    "alolan-vulpix": "vulpix-alola",
    "alolan-exeggutor": "exeggutor-alola",
    "alolan-marowak": "marowak-alola",
    "alolan-raichu": "raichu-alola",
    "alolan-sandshrew": "sandshrew-alola",
    "alolan-sandslash": "sandslash-alola",
    "alolan-meowth": "meowth-alola",
    "alolan-persian": "persian-alola",
    "alolan-grimer": "grimer-alola",
    "alolan-muk": "muk-alola",

    # PokéAPI uses "hisui" suffix; Smogon uses "-Hisui" (already handled by
    # basic slugging, kept here for clarity / future-proofing).
    # "samurott-hisui": "samurott-hisui",  # already correct — no exception needed

    # Smogon "Necrozma-Dawn Wings" has a space in the suffix.
    # basic_slug produces "necrozma-dawn-wings" which PokéAPI accepts — no exception needed.

    # PokéAPI uses "single-strike" suffix for base Urshifu form.
    # We leave "urshifu" as-is; pool construction handles the form distinction.

    # PokéAPI uses shortened names for Necrozma's fusions (not "-dusk-mane"/"-dawn-wings").
    "necrozma-dusk-mane": "necrozma-dusk",
    "necrozma-dawn-wings": "necrozma-dawn",

    # Base form names not in the PokéAPI /pokemon list — map to default variety.
    # Without these, fuzzy matching finds wrong forms (e.g. keldeo→keldeo-resolute).
    "toxtricity": "toxtricity-amped",
    "keldeo": "keldeo-ordinary",
    "giratina": "giratina-altered",
    "deoxys": "deoxys-normal",
    "urshifu": "urshifu-single-strike",
    "meloetta": "meloetta-aria",
    "enamorus": "enamorus-incarnate",
    "thundurus": "thundurus-incarnate",
    "tornadus": "tornadus-incarnate",
}


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def _basic_slug(name: str) -> str:
    """
    Convert any display name to a PokéAPI-style slug.

    Steps:
    1. NFD-normalize unicode and strip combining characters (removes accents).
    2. Lowercase and strip outer whitespace.
    3. Remove characters that aren't alphanumeric, spaces, or hyphens.
    4. Collapse runs of whitespace → single hyphen.
    5. Collapse runs of hyphens → single hyphen.
    6. Strip leading/trailing hyphens.
    """
    decomposed = unicodedata.normalize("NFD", name)
    ascii_only = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    s = ascii_only.lower().strip()
    s = re.sub(r"[^a-z0-9 \-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def normalize(name: str) -> str:
    """
    Return the PokéAPI slug for a Smogon display name.

    Applies _basic_slug first, then checks KNOWN_EXCEPTIONS.
    If the slug is in KNOWN_EXCEPTIONS the corrected value is returned.
    """
    slug = _basic_slug(name)
    corrected = KNOWN_EXCEPTIONS.get(slug)
    if corrected:
        log.debug("normalize: %r → %r (via exception)", name, corrected)
        return corrected
    return slug


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def fuzzy_match(
    slug: str,
    api_names: Collection[str],
    threshold: float = 90.0,
) -> tuple[str, float] | None:
    """
    Find the closest PokéAPI slug using rapidfuzz WRatio.

    Returns (best_match, score) if score >= threshold, else None.
    Logs a warning for any result below the threshold so it can be reviewed.
    """
    if not api_names:
        return None
    result = fz_process.extractOne(slug, api_names, scorer=fuzz.WRatio)
    if result is None:
        return None
    best, score, _ = result
    if score < threshold:
        log.warning(
            "Low-confidence fuzzy match: %r → %r (score=%.1f < %.0f) — review manually",
            slug, best, score, threshold,
        )
        return None
    return best, score


# ---------------------------------------------------------------------------
# Resolve: exact lookup with fuzzy fallback
# ---------------------------------------------------------------------------

def resolve(
    name: str,
    api_names: Collection[str],
    threshold: float = 90.0,
) -> str | None:
    """
    Map a Smogon display name to the canonical PokéAPI slug.

    1. Normalize → exact match in api_names → return immediately.
    2. Fuzzy-match fallback if exact lookup misses.
    3. Log a warning if the fuzzy score < threshold (match not returned).
    4. Log a warning if no match found at all.

    Returns the resolved PokéAPI slug, or None if resolution fails.
    """
    slug = normalize(name)
    api_set = api_names if isinstance(api_names, (set, frozenset)) else set(api_names)

    if slug in api_set:
        return slug

    log.debug("resolve: %r → slug %r not in API list, trying fuzzy", name, slug)
    match = fuzzy_match(slug, api_set, threshold=threshold)
    if match:
        best, score = match
        log.info("resolve: %r → %r via fuzzy (score=%.1f)", name, best, score)
        return best

    log.warning("resolve: no match for %r (slug=%r) — add to KNOWN_EXCEPTIONS or check spelling", name, slug)
    return None
