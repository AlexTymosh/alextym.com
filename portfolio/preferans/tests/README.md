# Preferans tests

PR 1 introduced the dependency-free static foundation check. PR 2 adds deterministic Python domain tests and randomized legal full-deal sequences. Future PRs add settlement golden fixtures, authorization/emulator tests and three-browser E2E tests.

From the repository root:

```powershell
node portfolio/preferans/tests/check-foundation.mjs
Push-Location backend
uv run python -m pytest ../portfolio/preferans/tests -q
Pop-Location
```

The domain's `conftest.py` temporarily supplies a test-only source path until PR 4 installs the backend package. Do not add a second authentication mechanism or public routes to make tests run.
