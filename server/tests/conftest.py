"""Keep imported server.main isolated from an exported host storage path."""

import os

os.environ.pop("DRAFT_SESSIONS_DIR", None)
