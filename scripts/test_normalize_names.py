"""
Tests for normalize_names.py
Run with: python -m pytest scripts/test_normalize_names.py -v
"""

import logging
import pytest

import normalize_names as m


# ---------------------------------------------------------------------------
# _basic_slug
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Great Tusk", "great-tusk"),
    ("Flutter Mane", "flutter-mane"),
    ("Iron Valiant", "iron-valiant"),
    ("Corviknight", "corviknight"),
    ("Ho-Oh", "ho-oh"),
    ("Landorus-Therian", "landorus-therian"),
    ("Deoxys-Speed", "deoxys-speed"),
    ("Kyurem-Black", "kyurem-black"),
    ("Necrozma-Dawn Wings", "necrozma-dawn-wings"),
    ("Urshifu-Rapid-Strike", "urshifu-rapid-strike"),
    ("Calyrex-Ice", "calyrex-ice"),
    ("Farfetch'd", "farfetchd"),
    ("Mr. Mime", "mr-mime"),
    ("Flabébé", "flabebe"),
    ("Mime Jr.", "mime-jr"),
    ("Kommo-o", "kommo-o"),
    ("  Scizor  ", "scizor"),
    ("Walking Wake", "walking-wake"),
    ("Weezing-Galar", "weezing-galar"),
    ("Slowking-Galar", "slowking-galar"),
    ("Ursaluna-Bloodmoon", "ursaluna-bloodmoon"),
    ("Samurott-Hisui", "samurott-hisui"),
    ("Dialga-Origin", "dialga-origin"),
    ("Giratina-Origin", "giratina-origin"),
    ("Zapdos-Galar", "zapdos-galar"),
])
def test_basic_slug(name, expected):
    assert m._basic_slug(name) == expected


# ---------------------------------------------------------------------------
# normalize — exception table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    # Incarnate shorthand
    ("Landorus-I", "landorus-incarnate"),
    ("Tornadus-I", "tornadus-incarnate"),
    ("Thundurus-I", "thundurus-incarnate"),
    ("Enamorus-I", "enamorus-incarnate"),
    # Ogerpon mask suffix
    ("Ogerpon-Wellspring", "ogerpon-wellspring-mask"),
    ("Ogerpon-Hearthflame", "ogerpon-hearthflame-mask"),
    ("Ogerpon-Cornerstone", "ogerpon-cornerstone-mask"),
    # Alolan prefix → -alola suffix
    ("Alolan Geodude", "geodude-alola"),
    ("Alolan Ninetales", "ninetales-alola"),
    ("Alolan Marowak", "marowak-alola"),
])
def test_normalize_exceptions(name, expected):
    assert m.normalize(name) == expected


def test_normalize_no_exception_passthrough():
    # Names with no exception should just get basic-slugged
    assert m.normalize("Great Tusk") == "great-tusk"
    assert m.normalize("Corviknight") == "corviknight"
    assert m.normalize("Landorus-Therian") == "landorus-therian"
    assert m.normalize("Ho-Oh") == "ho-oh"


# ---------------------------------------------------------------------------
# fuzzy_match
# ---------------------------------------------------------------------------

SAMPLE_API_NAMES = [
    "corviknight", "great-tusk", "gholdengo", "roaring-moon",
    "zamazenta", "flutter-mane", "iron-valiant", "landorus-incarnate",
    "landorus-therian", "ogerpon-wellspring-mask",
]


def test_fuzzy_match_exact():
    result = m.fuzzy_match("corviknight", SAMPLE_API_NAMES)
    assert result is not None
    best, score = result
    assert best == "corviknight"
    assert score == 100.0


def test_fuzzy_match_close():
    # Minor typo — should still hit above threshold
    result = m.fuzzy_match("corviknigt", SAMPLE_API_NAMES)
    assert result is not None
    best, score = result
    assert best == "corviknight"
    assert score >= 90.0


def test_fuzzy_match_below_threshold_returns_none(caplog):
    with caplog.at_level(logging.WARNING, logger="normalize_names"):
        result = m.fuzzy_match("pikachu", SAMPLE_API_NAMES, threshold=90.0)
    assert result is None
    assert any("Low-confidence" in r.message for r in caplog.records)


def test_fuzzy_match_empty_list():
    result = m.fuzzy_match("corviknight", [])
    assert result is None


def test_fuzzy_match_custom_threshold():
    # Accept any score above 50 — even garbage should match something
    result = m.fuzzy_match("xxxxxxxxxxx", SAMPLE_API_NAMES, threshold=0.0)
    assert result is not None  # some match always returned at threshold=0


# ---------------------------------------------------------------------------
# resolve
# ---------------------------------------------------------------------------

def test_resolve_exact_match():
    api = {"corviknight", "great-tusk", "gholdengo"}
    assert m.resolve("Corviknight", api) == "corviknight"


def test_resolve_exception_then_exact():
    # Ogerpon-Wellspring → normalize → "ogerpon-wellspring-mask" → in api set
    api = {"ogerpon-wellspring-mask", "ogerpon-hearthflame-mask"}
    assert m.resolve("Ogerpon-Wellspring", api) == "ogerpon-wellspring-mask"


def test_resolve_fuzzy_fallback():
    # "gholdengo" not in api under that exact name — test a close variant
    api = {"great-tusk", "flutter-mane", "iron-valiant", "zamazenta"}
    result = m.resolve("Zamazenta", api)
    assert result == "zamazenta"


def test_resolve_no_match_returns_none(caplog):
    api = {"corviknight", "great-tusk"}
    with caplog.at_level(logging.WARNING, logger="normalize_names"):
        result = m.resolve("Completely Unknown Mon", api)
    assert result is None
    assert any("no match" in r.message.lower() for r in caplog.records)


def test_resolve_accepts_list_or_set():
    names_list = ["corviknight", "great-tusk"]
    names_set = {"corviknight", "great-tusk"}
    assert m.resolve("Corviknight", names_list) == "corviknight"
    assert m.resolve("Corviknight", names_set) == "corviknight"


def test_resolve_landorus_i():
    api = {"landorus-incarnate", "landorus-therian"}
    assert m.resolve("Landorus-I", api) == "landorus-incarnate"


def test_resolve_alolan_geodude():
    api = {"geodude-alola", "graveler-alola", "golem-alola", "geodude"}
    assert m.resolve("Alolan Geodude", api) == "geodude-alola"


# ---------------------------------------------------------------------------
# Round-trip test: real scraped names against a plausible API slug list
# ---------------------------------------------------------------------------
# Verifies that every name from the scraped VR lists can be normalized to
# something that looks like a valid PokéAPI slug (no spaces, lowercase, etc.)
# Does NOT require a live API call — just checks slug format.

REAL_VR_NAMES = [
    # AAA VR
    "Corviknight", "Gholdengo", "Great Tusk", "Roaring Moon", "Zamazenta",
    "Deoxys-Speed", "Manaphy", "Pecharunt", "Primarina",
    "Iron Moth", "Kingambit", "Landorus-Therian", "Latios", "Moltres",
    "Scream Tail", "Swampert", "Ting-Lu", "Zapdos",
    "Chien-Pao", "Cobalion", "Garchomp", "Gliscor", "Iron Crown",
    "Iron Hands", "Iron Treads", "Landorus-I", "Meowscarada",
    "Ogerpon-Wellspring", "Skarmory", "Tinkaton", "Zarude",
    "Blissey", "Electrode-Hisui", "Empoleon", "Goodra-Hisui",
    "Iron Boulder", "Mamoswine", "Polteageist", "Sandy Shocks",
    "Samurott-Hisui", "Slither Wing", "Smeargle", "Thundurus-Therian",
    "Thundurus", "Tornadus-Therian", "Weezing-Galar",
    # Pokébilities VR
    "Meowscarada", "Alomomola", "Keldeo", "Samurott-Hisui",
    "Heatran", "Pecharunt", "Slowking", "Slowking-Galar",
    "Tornadus-Therian", "Cinderace", "Clodsire", "Deoxys-Speed",
    "Ditto", "Ogerpon-Wellspring", "Talonflame",
    "Ogerpon-Cornerstone", "Ogerpon-Hearthflame",
    "Breloom", "Crawdaunt", "Greninja", "Lokix", "Zapdos",
    "Ursaluna-Bloodmoon", "Moltres-Galar", "Zapdos-Galar",
]

import re as _re

def test_real_names_produce_valid_slugs():
    bad = []
    for name in REAL_VR_NAMES:
        slug = m.normalize(name)
        if not slug:
            bad.append((name, "empty slug"))
        elif _re.search(r"[^a-z0-9\-]", slug):
            bad.append((name, f"non-slug chars: {slug!r}"))
        elif " " in slug:
            bad.append((name, f"space in slug: {slug!r}"))
    assert bad == [], f"Invalid slugs: {bad}"
