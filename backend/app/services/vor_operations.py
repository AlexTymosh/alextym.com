"""Compatibility import: Fleet implementation belongs to portfolio/fleet_hub."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("fleet_hub.services.vor_operations")
