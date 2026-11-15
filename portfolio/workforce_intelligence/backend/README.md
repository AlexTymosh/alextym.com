# Workforce backend

One installable Python project under `src/workforce_intelligence`. The FastAPI
host imports `workforce_intelligence.router` and applies the Portfolio Lab
authorization dependency to all routes. The Workforce database and migrations
are project-owned. See [Workforce persistence](../docs/architecture.md) for its
path, history and reset contracts.
