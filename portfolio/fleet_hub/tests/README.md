# Fleet Hub tests (planned destination)

In PR 1, all existing tests remain in `backend/tests/`; this directory holds no executable tests yet.

Move relevant `test_vor_*.py`, including the SQLite seed contract, to a stable test location in the backend migration PR. Decide whether `pytest` collects directly from `portfolio/` or runs through a narrow host test adapter, then update CI **without dropping tests**.

Test categories: seed content/integrity, auth/session, workflow stages, contacts/subscribers, live-email allowlisting/quota, import/export, reconciliation, reporting, integration contracts, and host boundaries.
