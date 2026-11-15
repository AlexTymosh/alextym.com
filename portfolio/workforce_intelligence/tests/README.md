# Workforce tests

The shared backend pytest configuration runs the project manifest, SQLite
migrations and reset, controlled seed repeatability, and the mutation-to-metric
API tests. Tests use disposable databases and synthetic actors. The host tests
in `backend/tests/test_workforce_grants.py` exercise admission and project grants
at the authorisation boundary. Hosted verification remains part of the
Interview MVP release.
