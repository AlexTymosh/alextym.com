# Preferans backend (planned)

No backend module or live endpoints are created in PR 1. PR 2 adds a deterministic Python domain package without I/O; PR 4 introduces an installable package, Firebase-authorized FastAPI adapter, durable Firestore, and coordinated changes to the host `pyproject.toml`, `uv.lock`, and Dockerfile.

Do not expose `/api/preferans` until direct Render authentication and per-room authorization have been tested.
