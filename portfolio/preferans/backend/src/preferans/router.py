"""Public project API entry for the host. Domain remains independent."""

from .online.router import router
from .online.realtime_api import make_realtime_router

__all__ = ["router", "make_realtime_router"]
