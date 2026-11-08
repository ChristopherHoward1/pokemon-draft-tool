"""Build small, atomic PNG copies of the local sprites."""

import logging
import os
import tempfile
from pathlib import Path

SPRITES_DIR = Path(__file__).resolve().parent.parent / "sprites"
LOG = logging.getLogger(__name__)


def make_thumbnails(sprites_dir: Path = SPRITES_DIR) -> int:
    sources = list(sprites_dir.glob("*.png"))
    if not sources:
        return 0

    from PIL import Image

    thumbs_dir = sprites_dir / "thumbs"
    thumbs_dir.mkdir(exist_ok=True)
    failed = False
    for source in sources:
        target = thumbs_dir / source.name
        temp_path = None
        try:
            if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
                continue
            with Image.open(source) as image:
                image = image.convert("RGBA")
                image.thumbnail((128, 128), Image.Resampling.LANCZOS)
                with tempfile.NamedTemporaryFile(dir=thumbs_dir, suffix=".png", delete=False) as temp:
                    temp_path = Path(temp.name)
                image.save(temp_path, format="PNG", optimize=True)
            os.replace(temp_path, target)
        except (OSError, ValueError) as exc:
            LOG.warning("Could not make thumbnail for %s: %s", source, exc)
            failed = True
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    return int(failed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(make_thumbnails())
