"""Public Fleet startup hook used by the embedding FastAPI host.

The Fleet API's lazy database preparation remains available to standalone
router consumers and tests that do not run the host application's lifespan.
"""

from __future__ import annotations

import os


def prepare_demo_database() -> bool:
    """Initialize Fleet SQLite only when the optional demo is enabled.

    All schema and data changes use the existing guarded Fleet connection,
    v2 migration and operations bootstrap paths. Return False when disabled.
    This function is synchronous because SQLite initialization can block.
    """
    if os.getenv("VOR_DEMO_ENABLED", "false").lower() != "true":
        return False

    from fleet_hub.services import vor_data, vor_operations

    with vor_data.database() as db:
        vor_operations._setup(db)
    return True
