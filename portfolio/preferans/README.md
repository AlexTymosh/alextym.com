# Zaporizhzhia Preferans — portfolio module

**Status: PR 1–8 merged. PR 9 adds release-candidate privacy and security hardening. Production activation remains blocked pending real UAT and outstanding house-rule workflows.**

- Project ID: `preferans`
- Private route: `/portfolio/preferans`
- Feature-gated API prefix (mounted): `/api/preferans`
- Public portfolio card: disabled (`catalog.visible=false`)
- PR 1–8: merged as #268–#275; PR 9 branch: `feat/preferans-release`

The 2026-11-24 HTTP 503 repair fixes Python Admin SDK transaction reads and adds
regression coverage and safe storage diagnostics. The checked Render runtime
also needs a separate existing-role IAM correction for queries and writes.
See [evidence, permissions and deployment checks](docs/HTTP_503_FIRESTORE.ru.md).
Live IAM changes, deployment and production recovery remain operator actions.

## Boundaries

The website owns authentication, project grants, the guarded Next.js adapter and build/deploy wiring. Preferans owns its UI, future deterministic game domain, data schema, room rules, and tests. No direct Fleet/Workforce imports, separate credentials or standalone deployment.

`frontend/` hosts the project-owned React components and locally scoped CSS. `backend/src/preferans/domain/` contains a pure, side-effect-free rules engine. Authenticated Preferans API routes and server-only Firestore persistence adapters are implemented, but remain disabled until the feature flag and release gates are satisfied. `tests/` now contains the original foundation guard and deterministic Python engine tests. `docs/` holds both specifications and the engine contract.

## Read before writing code

1. [`SESSION_NOTES.md`](SESSION_NOTES.md)
2. [`docs/DEVELOPMENT_PLAN.ru.md`](docs/DEVELOPMENT_PLAN.ru.md)
3. [`docs/FULL_TECHNICAL_SPECIFICATION.ru.md`](docs/FULL_TECHNICAL_SPECIFICATION.ru.md)
4. [`docs/HOUSE_RULES.ru.md`](docs/HOUSE_RULES.ru.md)
5. [`docs/DOMAIN_ENGINE.ru.md`](docs/DOMAIN_ENGINE.ru.md)
6. [`../../docs/architecture/portfolio.md`](../../docs/architecture/portfolio.md)

## Focused checks (repo root)

```bash
node scripts/check-portfolio-registry.mjs
node scripts/check-registered-project-boundaries.mjs
node portfolio/preferans/tests/check-foundation.mjs
node scripts/check-no-raw-cyrillic.mjs
task repo:check
# from backend/: uv run python -m pytest ../portfolio/preferans/tests -q
```

The raw Cyrillic check examines tracked files; stage newly added files before relying on its result. Run the entire `task ci` before PR review. No successful CI result is claimed by this README.

## Access

The route returns 404 if Portfolio Lab is disabled. When enabled, the shared project-grant check allows only granted users (Owner inherits access). The shell does not expose rooms, player data, cards, game APIs or secrets. Further controls and endpoints require additional backend protection and review.

## PR 4 — private rooms (feature gated)

The room API is implemented behind `PREFERANS_ROOMS_ENABLED=true`; default is disabled. It uses Firebase Portfolio Lab access, transactional server-only Firestore storage, strict per-player projections and idempotent command receipts. The browser has no direct Firestore read/write access. See `docs/SECURE_ROOMS.ru.md`, `docs/HOUSE_RULES_DECISIONS.ru.md`, `docs/PR04_RUNBOOK.ru.md`. The interactive table is still planned for PR 5.

## PR 5 — private interactive game UI

With the Portfolio Lab and Preferans room feature flags enabled, the project page
now offers a responsive three-player table. Firestore remains server-only;
`View` users cannot create/join games. See `docs/PR05_GAME_UI.ru.md`.
The flag is off by default; no existing public website routes change.


## PR 7 history and ranking

The game now records one immutable result and three atomic ranking updates when a room closes normally. The guarded history/rankings endpoints and responsive table/three-line graph live under the same existing Next.js and FastAPI feature flags. See [`docs/PR07_HISTORY_RANKING.ru.md`](docs/PR07_HISTORY_RANKING.ru.md). User-accepted sheet discard, punishment substitution choices, real Firestore emulator UAT and opt-in media are not implemented.

## PR 8 communication and nostalgia

Private three-peer WebRTC with separate camera/microphone controls, recipient-scoped Firestore SDP/ICE signalling, unanimous recording votes and initiator-only local recording are implemented behind separate feature flags, off by default. Generated unidentifiable apartment artwork is bundled as `nostalgic-room.webp`; no private photographs are used. Before enabling in production follow `docs/PR08_MEDIA.ru.md` and `docs/PR08_UAT.ru.md` and resolve WebRTC NAT, recording revocation and Firestore quota/storage risks.

## PR 9 release candidate and operator checklist

The media recorder now stops when browser consent can no longer be confirmed, signaling has explicit expiry and uses dedicated `preferans_media` / `preferans_media_ops` collections. For strict £0, **do not activate paid managed Firestore TTL**; the explicit maintenance script is `backend/scripts/cleanup_media.py` and requires an operator. `docs/PR09_RELEASE_CANDIDATE.ru.md` contains staging flags, storage cost estimates and rollback; `docs/PR09_UAT.ru.md` is the mandatory three-user acceptance checklist. Project flags and catalog visibility remain off until UAT and Owner sign-off. Not all historical house-rule workflows are implemented.
