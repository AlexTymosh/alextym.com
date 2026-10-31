"""Locate the embedded Fleet package during direct pytest collection."""

from pathlib import Path
import sys

_FLEET_SRC = Path(__file__).resolve().parents[1] / "backend/src"
if str(_FLEET_SRC) not in sys.path:
    sys.path.insert(0, str(_FLEET_SRC))
