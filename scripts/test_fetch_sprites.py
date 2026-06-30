"""
Tests for fetch_sprites.py.
All HTTP calls and filesystem writes are mocked.
Run with: python -m pytest scripts/test_fetch_sprites.py -v
"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import fetch_sprites as m


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_pool(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


def _make_entry(dex_id: int, name: str = "poke") -> dict:
    return {
        "dex_id": dex_id,
        "name": name,
        "display_name": name.title(),
        "types": ["normal"],
        "base_stat_total": 300,
        "vr_tier": "Unranked",
        "sprite_path": f"sprites/{dex_id}.png",
        "format": "aaa",
    }


def _ok_response(content: bytes = b"PNG") -> MagicMock:
    r = MagicMock()
    r.content = content
    r.raise_for_status = MagicMock()
    return r


def _error_response(status: int = 404) -> MagicMock:
    import requests
    r = MagicMock()
    r.raise_for_status.side_effect = requests.HTTPError(f"{status} Error")
    return r


# ---------------------------------------------------------------------------
# collect_dex_ids
# ---------------------------------------------------------------------------

def test_collect_dex_ids_single_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "pool.json"
        _write_pool(p, [_make_entry(1), _make_entry(2), _make_entry(3)])
        result = m.collect_dex_ids([p])
    assert result == [1, 2, 3]


def test_collect_dex_ids_deduplicates_across_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = Path(tmpdir) / "aaa.json"
        p2 = Path(tmpdir) / "pokebilities.json"
        _write_pool(p1, [_make_entry(1), _make_entry(2)])
        _write_pool(p2, [_make_entry(2), _make_entry(3)])
        result = m.collect_dex_ids([p1, p2])
    assert result == [1, 2, 3]


def test_collect_dex_ids_sorted():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "pool.json"
        _write_pool(p, [_make_entry(997), _make_entry(1), _make_entry(248)])
        result = m.collect_dex_ids([p])
    assert result == [1, 248, 997]


def test_collect_dex_ids_missing_file_warns(caplog, tmp_path):
    missing = tmp_path / "nonexistent.json"
    with caplog.at_level(logging.WARNING, logger="fetch_sprites"):
        result = m.collect_dex_ids([missing])
    assert result == []
    assert any("not found" in r.message.lower() for r in caplog.records)


def test_collect_dex_ids_empty_pool():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "pool.json"
        _write_pool(p, [])
        result = m.collect_dex_ids([p])
    assert result == []


# ---------------------------------------------------------------------------
# download_sprite
# ---------------------------------------------------------------------------

def test_download_sprite_skips_existing(tmp_path):
    dest = tmp_path / "879.png"
    dest.write_bytes(b"existing")
    with patch("fetch_sprites.requests.get") as mock_get:
        result = m.download_sprite(879, tmp_path)
    mock_get.assert_not_called()
    assert result is True
    assert dest.read_bytes() == b"existing"  # unchanged


def test_download_sprite_success(tmp_path):
    with patch("fetch_sprites.requests.get", return_value=_ok_response(b"PNG_BYTES")) as mock_get:
        with patch("fetch_sprites.time.sleep"):
            result = m.download_sprite(879, tmp_path)
    assert result is True
    assert (tmp_path / "879.png").read_bytes() == b"PNG_BYTES"
    mock_get.assert_called_once()
    url_called = mock_get.call_args[0][0]
    assert "879" in url_called
    assert "official-artwork" in url_called


def test_download_sprite_404_returns_false(tmp_path, caplog):
    with patch("fetch_sprites.requests.get", return_value=_error_response(404)):
        with patch("fetch_sprites.time.sleep"):
            with caplog.at_level(logging.WARNING, logger="fetch_sprites"):
                result = m.download_sprite(9999, tmp_path)
    assert result is False
    assert not (tmp_path / "9999.png").exists()
    assert any("9999" in r.message for r in caplog.records)


def test_download_sprite_network_error_returns_false(tmp_path):
    import requests
    with patch("fetch_sprites.requests.get", side_effect=requests.ConnectionError("timeout")):
        with patch("fetch_sprites.time.sleep"):
            result = m.download_sprite(1, tmp_path)
    assert result is False


def test_download_sprite_url_contains_dex_id(tmp_path):
    with patch("fetch_sprites.requests.get", return_value=_ok_response()) as mock_get:
        with patch("fetch_sprites.time.sleep"):
            m.download_sprite(10272, tmp_path)
    url = mock_get.call_args[0][0]
    assert "10272" in url


def test_download_sprite_rate_limited(tmp_path):
    with patch("fetch_sprites.requests.get", return_value=_ok_response()):
        with patch("fetch_sprites.time.sleep") as mock_sleep:
            m.download_sprite(1, tmp_path)
    mock_sleep.assert_called_once()


# ---------------------------------------------------------------------------
# fetch_all
# ---------------------------------------------------------------------------

def test_fetch_all_downloads_missing(tmp_path):
    with patch("fetch_sprites.download_sprite", return_value=True) as mock_dl:
        summary = m.fetch_all([1, 2, 3], tmp_path)
    assert mock_dl.call_count == 3
    assert summary["downloaded"] == 3
    assert summary["skipped"] == 0
    assert summary["failed"] == 0


def test_fetch_all_skips_existing(tmp_path):
    (tmp_path / "1.png").write_bytes(b"x")
    (tmp_path / "2.png").write_bytes(b"x")
    with patch("fetch_sprites.download_sprite", return_value=True) as mock_dl:
        summary = m.fetch_all([1, 2, 3], tmp_path)
    # Only dex_id=3 should be attempted (1 and 2 already exist)
    mock_dl.assert_called_once_with(3, tmp_path)
    assert summary["skipped"] == 2
    assert summary["downloaded"] == 1


def test_fetch_all_counts_failures(tmp_path):
    def _side_effect(dex_id, sprites_dir):
        return dex_id != 999  # 999 fails

    with patch("fetch_sprites.download_sprite", side_effect=_side_effect):
        summary = m.fetch_all([1, 999, 2], tmp_path)
    assert summary["downloaded"] == 2
    assert summary["failed"] == 1


def test_fetch_all_creates_sprites_dir(tmp_path):
    sprites = tmp_path / "sprites"
    assert not sprites.exists()
    with patch("fetch_sprites.download_sprite", return_value=True):
        m.fetch_all([1], sprites)
    assert sprites.exists()


def test_fetch_all_empty_list(tmp_path):
    summary = m.fetch_all([], tmp_path)
    assert summary == {"downloaded": 0, "skipped": 0, "failed": 0}
