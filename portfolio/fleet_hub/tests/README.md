# Fleet Hub backend tests

The original 16 tests were moved from `backend/tests/` during PR 3, with
only import path and seed-location updates. A new wiring regression test verifies
one FastAPI Fleet registration, compatibility imports, and stable SQLite paths. They are collected once by
`backend/pyproject.toml`'s `pytest testpaths` and run in the existing
`task backend:check` / GitHub CI backend job.

Tests cover authentication, vehicle data, workflows, reconciliation, subscribers,
export formats, security rules, and exact approved synthetic seed integrity.
Do not remove tests to make CI pass. Keep test SQLite in pytest `tmp_path`.
