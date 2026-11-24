# Preferans — session notes

## Current candidate: PR14.A — technical finish and release acceptance

Base: `eab5354e6e1d92427a1f2254216f590ae7b2b667` (PR13.D merged; green CI reported by Owner).
Branch: `feat/preferans-modernization-release`.

- Implemented voluntary sheet discard and recipient-only offer/accept/refuse.
- Reused the existing atomic result/ranking transaction; unfinished ledger is not settled.
- Added terminal view and explicit UI confirmation; old offers expire with the deal.
- Added pure tests, store integration tests, TS model checks and simulated 6h/8h hub tests.
- Added offline release-evidence evaluator and acceptance documentation.
- Isolated checks: 8 pure, 4 evidence and 2 simulated hub scenarios. Full repository CI and real-device/emulator/production acceptance pending.
- No deployment, provider configuration changes, paid infrastructure or video recording.
- Remaining: G02b, parts of G07, G08, real measurements and acceptance gates (G10).

See `docs/PR14_RELEASE_ACCEPTANCE.ru.md`, `docs/MODERNIZATION_GAP_REGISTER.ru.md` and `docs/MODERNIZATION_DEVELOPMENT_PLAN.ru.md`.

Next: apply candidate, run full checks, inspect diff, commit and review. Continue functional gaps and collect actual release evidence before enabling the new production capabilities.
