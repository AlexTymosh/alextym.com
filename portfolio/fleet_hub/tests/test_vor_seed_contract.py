"""Approved Fleet VOR Hub v2 seed on Render Free; no legacy v1 dependency."""

import hashlib
import sqlite3
from fleet_hub.services.vor_store import SEED_FILE as SEED

SHA256 = "db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532"


def test_seed_matches_approved_local_database():
    assert SEED.is_file()
    assert hashlib.sha256(SEED.read_bytes()).hexdigest() == SHA256
    with sqlite3.connect(SEED.as_uri() + "?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
        assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 42
        garage, owner = db.execute(
            "SELECT garage, responsible FROM vehicles WHERE registration='GX24 KLM'"
        ).fetchone()
        assert (garage, owner) == ("Basingstoke", "Jason W.")
