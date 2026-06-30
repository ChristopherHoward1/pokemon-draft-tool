"""
Tests for scrape_smogon.py.

Unit tests use synthetic HTML that mirrors the actual Smogon structure.
Integration tests run against cached real HTML (data/raw/).
Run with: python -m pytest scripts/test_scrape_smogon.py -v
"""

import json
from pathlib import Path
import tempfile
import pytest

import scrape_smogon as m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _forum_page(*posts_html: str) -> str:
    """Wrap post bodies in XenForo-like article > message-body > bbWrapper."""
    articles = ""
    for i, body in enumerate(posts_html):
        pid = f"post-{1000 + i}"
        articles += f"""
        <article data-content="{pid}" id="js-{pid}">
          <div class="message-body">
            <div class="bbWrapper">{body}</div>
          </div>
        </article>
        """
    return f"<html><body>{articles}</body></html>"


def _dex_page(description_html: str) -> str:
    payload = json.dumps({
        "description": description_html,
        "overview": "",
        "resources": [],
        "pokemon_with_strategies": [],
    })
    rpc_list = json.dumps([["[\"dump-format\",{}]", json.loads(payload)]])
    settings = json.dumps({"injectRpcs": json.loads(rpc_list), "procSettings": {}, "ads": {}})
    return f"<html><body><script>dexSettings = {settings};</script></body></html>"


def _run_vr(html: str, format_name: str = "test", post_index: int = 0) -> list:
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / f"{format_name}_vr.html").write_text(html, encoding="utf-8")
        try:
            return m.scrape_vr_thread("http://unused", format_name, post_index=post_index)
        finally:
            m.RAW_DIR = orig


def _run_bans_spoiler(html: str, format_name: str = "test", post_index: int = 0) -> set:
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / f"{format_name}_bans.html").write_text(html, encoding="utf-8")
        try:
            return m.scrape_ban_spoiler("http://unused", format_name, post_index=post_index)
        finally:
            m.RAW_DIR = orig


def _run_bans_dex(html: str, format_name: str = "test") -> set:
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / f"{format_name}_bans_dex.html").write_text(html, encoding="utf-8")
        try:
            return m.scrape_ban_dex("http://unused", format_name)
        finally:
            m.RAW_DIR = orig


# ---------------------------------------------------------------------------
# _normalise_tier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("S", "S"),
    ("S Rank", "S"),
    ("S RANK : Metagame-Defining threats", "S"),
    ("A+", "A+"),
    ("A", "A"),
    ("A-", "A-"),
    ("A RANK : Important Pokemon in the tier", "A"),
    ("B+", "B+"),
    ("B", "B"),
    ("B-", "B-"),
    ("B RANK : Pokemon with valuable roles", "B"),
    ("C+", "C+"),
    ("C", "C"),
    ("C-", "C-"),
    ("C RANK : ...", "C"),
    ("D", "D"),
    ("Unranked", "Unranked"),
    ("UNRANKED", "Unranked"),
])
def test_normalise_tier_matches(raw, expected):
    assert m._normalise_tier(raw) == expected


@pytest.mark.parametrize("raw", [
    "Corviknight",
    "Alomomola",
    "Archaludon",
    "POKEMON : Grouped into tiers",
    "CHOSEN ABILITIES : Sorted alphabetically",
    "Pokémon",
    "Abilities",
    "",
    "   ",
])
def test_normalise_tier_no_match(raw):
    assert m._normalise_tier(raw) is None


# ---------------------------------------------------------------------------
# VR table parser — synthetic HTML mirroring real Smogon structure
# ---------------------------------------------------------------------------

VR_TABLE_POKEBILITIES = _forum_page(
    # post 0: intro (irrelevant)
    "<p>What is PokeAAA?</p>",
    # post 1: FAQ
    "<p>FAQ</p>",
    # post 2: sample teams
    "<p>Sample Teams</p>",
    # post 3: the VR table
    """
    <table>
      <tr><td>POKEMON : Grouped into tiers</td><td>CHOSEN ABILITIES</td></tr>
      <tr><td>S RANK : Metagame-Defining threats</td><td></td></tr>
      <tr><td><img alt=":corviknight:"> Corviknight</td><td>Delta Stream, Fluffy</td></tr>
      <tr><td><img alt=":meowscarada:"> Meowscarada</td><td>Sword of Ruin</td></tr>
      <tr><td></td><td></td></tr>
      <tr><td>A RANK : Important Pokemon</td><td></td></tr>
      <tr><td>A+</td><td></td></tr>
      <tr><td><img alt=":alomomola:"> Alomomola</td><td>Fluffy</td></tr>
      <tr><td>A</td><td></td></tr>
      <tr><td><img alt=":heatran:"> Heatran</td><td>Desolate Land</td></tr>
      <tr><td>A-</td><td></td></tr>
      <tr><td><img alt=":garchomp:"> Garchomp</td><td>Regenerator</td></tr>
      <tr><td>B RANK : Solid options</td><td></td></tr>
      <tr><td>B+</td><td></td></tr>
      <tr><td><img alt=":greninja:"> Greninja</td><td>Adaptability</td></tr>
    </table>
    """,
)

VR_TABLE_AAA = _forum_page(
    # post 0: the VR table (post-1000 = first article)
    """
    <table>
      <tr><td></td><td>Pokémon</td><td>Abilities</td></tr>
      <tr><td>S Rank</td><td></td><td></td></tr>
      <tr><td>A Rank</td><td></td><td></td></tr>
      <tr><td>A+</td><td></td><td></td></tr>
      <tr><td>Corviknight</td><td>Corviknight</td><td>Intimidate, Fluffy</td></tr>
      <tr><td>Gholdengo</td><td>Gholdengo</td><td>Magic Guard</td></tr>
      <tr><td>A</td><td></td><td></td></tr>
      <tr><td>Deoxys-Speed</td><td>Deoxys-Speed</td><td>Sheer Force</td></tr>
      <tr><td>B Rank</td><td></td><td></td></tr>
      <tr><td>B+</td><td></td><td></td></tr>
      <tr><td>Chien-Pao</td><td>Chien-Pao</td><td>Sword of Ruin</td></tr>
    </table>
    """,
)


def test_vr_pokebilities_s_tier():
    entries = _run_vr(VR_TABLE_POKEBILITIES, post_index=3)
    s = [e.name for e in entries if e.vr_tier == "S"]
    assert "Corviknight" in s
    assert "Meowscarada" in s


def test_vr_pokebilities_a_plus_tier():
    entries = _run_vr(VR_TABLE_POKEBILITIES, post_index=3)
    a_plus = [e.name for e in entries if e.vr_tier == "A+"]
    assert "Alomomola" in a_plus


def test_vr_pokebilities_a_minus_tier():
    entries = _run_vr(VR_TABLE_POKEBILITIES, post_index=3)
    a_minus = [e.name for e in entries if e.vr_tier == "A-"]
    assert "Garchomp" in a_minus


def test_vr_aaa_a_plus_tier():
    entries = _run_vr(VR_TABLE_AAA, post_index=0)
    a_plus = [e.name for e in entries if e.vr_tier == "A+"]
    assert "Corviknight" in a_plus
    assert "Gholdengo" in a_plus


def test_vr_aaa_no_s_tier_pokemon():
    # AAA has an empty S Rank — no pokemon should be assigned to S
    entries = _run_vr(VR_TABLE_AAA, post_index=0)
    s = [e for e in entries if e.vr_tier == "S"]
    assert s == []


def test_vr_aaa_b_plus_tier():
    entries = _run_vr(VR_TABLE_AAA, post_index=0)
    b_plus = [e.name for e in entries if e.vr_tier == "B+"]
    assert "Chien-Pao" in b_plus


def test_vr_empty_table_no_crash():
    html = _forum_page("<table><tr><td></td></tr></table>")
    entries = _run_vr(html, post_index=0)
    assert isinstance(entries, list)


def test_vr_wrong_post_index_no_crash():
    html = _forum_page("<p>Nothing useful</p>")
    entries = _run_vr(html, post_index=99)
    assert isinstance(entries, list)


# ---------------------------------------------------------------------------
# Ban list — spoiler format (Pokébilities)
# ---------------------------------------------------------------------------

BAN_SPOILER_HTML = _forum_page("""
<div class="bbCodeSpoiler">
  <button>Banned Pokemon</button>
  <div class="bbCodeSpoiler-content">
    <div class="bbCodeBlock bbCodeBlock--spoiler">
      <div class="bbCodeBlock-content">
        <img alt=":annihilape:" class="smilie"/> Annihilape<br/>
        <img alt=":flutter-mane:" class="smilie"/> Flutter Mane<br/>
        <img alt=":calyrex-shadow:" class="smilie"/> Calyrex-Shadow<br/>
      </div>
    </div>
  </div>
</div>
""")


def test_ban_spoiler_names():
    banned = _run_bans_spoiler(BAN_SPOILER_HTML)
    assert "Annihilape" in banned
    assert "Flutter Mane" in banned
    assert "Calyrex-Shadow" in banned


def test_ban_spoiler_no_spoiler_no_crash():
    html = _forum_page("<p>No spoiler here</p>")
    banned = _run_bans_spoiler(html)
    assert isinstance(banned, set)


# ---------------------------------------------------------------------------
# Ban list — dex format (AAA)
# ---------------------------------------------------------------------------

BAN_DEX_DESCRIPTION = """
<h2>Play Restrictions</h2>
<ul><li><strong>Species Clause</strong>: description</li></ul>
<h3>Pokémon Restrictions</h3>
<p>Players cannot use these Pokémon:</p>
<ul>
  <li><a href="/dex/sv/pokemon/annihilape/">Annihilape</a></li>
  <li><a href="/dex/sv/pokemon/flutter-mane/">Flutter Mane</a></li>
  <li><a href="/dex/sv/pokemon/calyrex-shadow/">Calyrex-Shadow</a></li>
  <li><a href="/dex/sv/pokemon/zacian-crowned/">Zacian-Crowned</a></li>
</ul>
<h3>Ability Restrictions</h3>
<ul>
  <li><a href="/dex/sv/abilities/arena-trap/">Arena Trap</a></li>
</ul>
"""


def test_ban_dex_pokemon_names():
    html = _dex_page(BAN_DEX_DESCRIPTION)
    banned = _run_bans_dex(html)
    assert "Annihilape" in banned
    assert "Flutter Mane" in banned
    assert "Calyrex-Shadow" in banned
    assert "Zacian-Crowned" in banned


def test_ban_dex_abilities_not_included():
    html = _dex_page(BAN_DEX_DESCRIPTION)
    banned = _run_bans_dex(html)
    # Ability bans should not appear in the pokemon ban set
    assert "Arena Trap" not in banned


def test_ban_dex_no_settings_no_crash():
    html = "<html><body><p>No dexSettings here</p></body></html>"
    banned = _run_bans_dex(html)
    assert isinstance(banned, set)


# ---------------------------------------------------------------------------
# Integration tests — real cached HTML (skipped if cache missing)
# ---------------------------------------------------------------------------

REAL_POKE_VR = Path("data/raw/pokebilities_raw.html")
REAL_AAA_VR = Path("data/raw/aaa_raw.html")
REAL_AAA_BANS = Path("data/raw/aaa_banlist_dex.html")


@pytest.mark.skipif(not REAL_POKE_VR.exists(), reason="cached HTML not present")
def test_integration_pokebilities_vr():
    html = REAL_POKE_VR.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / "pokebilities_vr.html").write_text(html, encoding="utf-8")
        try:
            entries = m.scrape_vr_thread("http://unused", "pokebilities", post_index=3)
        finally:
            m.RAW_DIR = orig

    assert len(entries) > 10, "Expected at least 10 VR entries"
    tiers = {e.vr_tier for e in entries}
    assert "S" in tiers
    names = [e.name for e in entries]
    assert "Corviknight" in names
    assert "Meowscarada" in names


@pytest.mark.skipif(not REAL_AAA_VR.exists(), reason="cached HTML not present")
def test_integration_aaa_vr():
    html = REAL_AAA_VR.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / "aaa_vr.html").write_text(html, encoding="utf-8")
        try:
            entries = m.scrape_vr_thread(
                "http://unused", "aaa",
                post_index=0, post_id="post-9390607",
            )
        finally:
            m.RAW_DIR = orig

    assert len(entries) > 20, "Expected at least 20 VR entries"
    names = [e.name for e in entries]
    assert "Corviknight" in names
    a_plus = [e for e in entries if e.vr_tier == "A+"]
    assert len(a_plus) >= 3


@pytest.mark.skipif(not REAL_POKE_VR.exists(), reason="cached HTML not present")
def test_integration_pokebilities_bans():
    html = REAL_POKE_VR.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / "pokebilities_bans.html").write_text(html, encoding="utf-8")
        try:
            banned = m.scrape_ban_spoiler("http://unused", "pokebilities", post_index=0)
        finally:
            m.RAW_DIR = orig

    assert len(banned) > 20, "Expected at least 20 banned Pokémon"
    assert "Annihilape" in banned


@pytest.mark.skipif(not REAL_AAA_BANS.exists(), reason="cached HTML not present")
def test_integration_aaa_bans():
    html = REAL_AAA_BANS.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = m.RAW_DIR
        m.RAW_DIR = Path(tmpdir)
        (Path(tmpdir) / "aaa_bans_dex.html").write_text(html, encoding="utf-8")
        try:
            banned = m.scrape_ban_dex("http://unused", "aaa")
        finally:
            m.RAW_DIR = orig

    assert len(banned) > 20, "Expected at least 20 banned Pokémon"
    assert "Annihilape" in banned
    assert "Flutter Mane" in banned
