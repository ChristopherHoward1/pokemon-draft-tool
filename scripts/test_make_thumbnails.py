"""Thumbnail pipeline behavior, using temporary sprite directories."""

import os
import sys
from unittest.mock import patch

import make_thumbnails as m
from PIL import Image


def test_rgba_thumbnail_and_mtimes(tmp_path):
    sprites = tmp_path / "sprites"
    sprites.mkdir()
    source = sprites / "a.png"
    Image.new("RGBA", (475, 475), (255, 0, 0, 100)).save(source)

    assert m.make_thumbnails(sprites) == 0
    thumb = sprites / "thumbs" / "a.png"
    with Image.open(thumb) as image:
        assert image.size == (128, 128)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 100

    first_mtime = thumb.stat().st_mtime_ns
    assert m.make_thumbnails(sprites) == 0
    assert thumb.stat().st_mtime_ns == first_mtime

    os.utime(source, ns=(first_mtime + 2_000_000_000,) * 2)
    assert m.make_thumbnails(sprites) == 0
    assert thumb.stat().st_mtime_ns > first_mtime


def test_bad_source_does_not_stop_others_or_leave_partial_file(tmp_path, caplog):
    sprites = tmp_path / "sprites"
    sprites.mkdir()
    (sprites / "bad.png").write_bytes(b"not a PNG")
    Image.new("RGBA", (475, 475)).save(sprites / "good.png")

    assert m.make_thumbnails(sprites) == 1
    assert (sprites / "thumbs" / "good.png").is_file()
    assert [p.name for p in (sprites / "thumbs").iterdir()] == ["good.png"]
    assert "bad.png" in caplog.text


def test_missing_and_empty_sprites_need_no_pillow(tmp_path):
    with patch.dict(sys.modules, {"PIL": None}):
        assert m.make_thumbnails(tmp_path / "missing") == 0
        empty = tmp_path / "empty"
        empty.mkdir()
        assert m.make_thumbnails(empty) == 0
