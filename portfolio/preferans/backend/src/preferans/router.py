"""Public project API entry for the host. Domain remains independent."""

from .online.router import router

__all__ = ["router"]
