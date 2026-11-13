# Workforce backend

One installable Python project under `src/workforce_intelligence`. Only `workforce_intelligence.router` is imported by the FastAPI host. The current namespace exposes a denied status probe; all requests return 404 until shared project authorization is available. No SQLite bootstrap, data tables or APIs are deployed in this first commit. Future persistence, migration and seed implementations belong exclusively to this package.
