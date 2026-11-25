# Preferans — session notes

Version 2.7 | 2026-11-24 | Project only.

- PR10–13.D and PR14.A merged; inspected main `50eddd404fa5e320f04da58c942d13b426e9de71`. Owner reports green local CI. Hosted checks observed: seven success and frontend running at inspection; check final head before release. No verified production activation or real 6/8h device/provider evidence.
- PR14.B1 candidate `feat/preferans-seat-swap`: unanimous swap of two occupied seats before the first deal, recipient/third-player consent, rejection preserves setup, successful swap resets readiness and retains selected dealer identity. Revokes old room tickets, leases, views and ephemeral media after commit; recoverable seat mismatch, fresh projection/reconnect, profile cache seat_revision. Existing ledger, admin UID, game rules and host guard unchanged. No automatic migration of legacy lobbies. No recording, billing or provider setting changes.
- Local isolated evidence: 17 pure/hub Python cases (hub reconstructed from earlier overlays), 8 model assertions and ES5 strict compile, exact-context checks. Actual full checkout/transaction tests, hosted CI for candidate, real socket/browser/Emulator tests not run here. See `docs/PR14_SEAT_SWAP.ru.md`.
- Next smallest task after Owner applies, tests, commits and merges: remaining G07 accidental reveal unanimous decisions (continue/redeal/penalty, preserve accounting/audit and pause invariants), then immutable punishment choices and G08 rules/archive. Read HOUSE_RULES and full specification before coding; no invented house rules. G10 real-device/core/media acceptance, 6/8h measurements and explicit release approval remain mandatory. Root SESSION_NOTES untouched. No remote changes by assistant.

## 2026-11-25 — PR14 final workflows candidate

PR14.B1 is merged in the pinned base. PR14.B2–B4 implementation candidate and PR14.C acceptance checklist: see `docs/PR14_FINAL_WORKFLOWS.ru.md`. Full CI, emulator, real-device soak and release approval remain pending. No production flags changed.

## 2026-11-25 — PR15 immersive table candidate

Base: `e1abf5b5de47e7582f94f37086cd1846c123e380` (PR #286 merged). One PR, logical commits. See `docs/PR15_IMMERSIVE_TABLE.ru.md` for new UI, privacy, dealer and notebook decisions. The original game engine and scoring formula remain unchanged. Installer uses exact base and unique anchors; isolated checks do not establish full CI or production acceptance. Owner must verify the full checkout, Firebase Emulator, three-client interactions, card artwork and notebook appearance. PR14.C / G10 release evidence remains pending. No remote mutation or production flag changes.

## 2026-11-25 - PR15 CI corrections (PR #287)

CI run 45621397635 stopped at Ruff formatting, frontend typecheck and the website shell boundary check. The patch removes unreachable room-view access in the invitation bar and preserves the static site-main class with a route-scoped data attribute for the Preferans width. Ruff formatting must be applied with uv. The Cyrillic guard passed all eight tests. Full backend tests, frontend build and browser tests are still required. No change to production flags or game rules. Local verification may use direct uv, Node, npm and Docker commands without Task.

## 2026-11-25 — PR16 table experience follow-up

PR #287 merged at `e1f669a981f74925d6153b2d2b595031eab991e0`. Follow-up candidate removes play confirmation UI, adds pointer ghost, 1.3s trick display, larger table/player tiles, per-seat last won trick, authoritative activity timestamp, table themes and compact settlement choices. Active HTTP fallback is 4s; socket loop is 75ms, not a guaranteed end-to-end latency. Real CC0 atlas PNGs must be downloaded by the installer and committed with their source manifest. The installer accepts both official Wikimedia media hosts, requests standard 330px thumbnails, and verifies the destination of redirects. The initial import failed before writing project files because the new thumbnail hostname was not allow-listed. No deployment or provider changes. Full CI without Task, real three-browser latency/animation and visual acceptance remain pending. Existing full scoring engine remains unchanged. Local UI chooses POOL for open regular pools; for a passout reward crossing the pool target with hill present, the remaining amount defaults to HILL_FIRST. This intentionally removes the previously available route choice in that case, per the requested simplified UI. The settlement button remains for the admin.

## 2026-11-25 — PR17 table refinements candidate

Base: e108b3bc1eba84585c9edb67a1e9fa3bca3e1ca2 (PR #288 merged). Owner feedback: icon rail must stay collapsed; source-backed FAQ; global last trick only (shared replay where enabled); larger cards, video tiles and alternating trick trains; compact notebook; invalid drop feedback; fullscreen header control. Existing licensed artwork, preferences, scoring and auth are unchanged. Publish notifications wake existing WebSockets immediately, retaining the 75 ms idle check and existing HTTP fallback; no extra Firestore operations are introduced by the notifier. Actual latency, CPU/hosting cost and responsive visual acceptance must be measured on three clients. FAQ snapshot must match both rule documents. Full CI, Emulator and release acceptance remain pending. No remote mutation or production configuration changes.
