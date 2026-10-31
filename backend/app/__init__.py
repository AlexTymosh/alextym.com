"""alextym backend application package.

Expose embedded portfolio Python sources to the common FastAPI host. This
explicit source bridge avoids a separate application/server and preserves the
existing backend/uv.lock and the Render Free deployment architecture.
"""

from pathlib import Path
import sys

_FLEET_BACKEND_SRC = Path(__file__).resolve().parents[2] / "portfolio/fleet_hub/backend/src"
if not _FLEET_BACKEND_SRC.is_dir():
    raise RuntimeError(f"Embedded Fleet backend source is missing: {_FLEET_BACKEND_SRC}")
if str(_FLEET_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_FLEET_BACKEND_SRC))
