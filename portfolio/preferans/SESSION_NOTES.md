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

## 2026-11-25 — PR18 table polish candidate

Base: 8e8aaf555e43624b1b93aa04e8bd5e9ff9818eab (PR17). Actual trick collection target is the latest bundle of the winning seat; dealing originates at the field center and takes approximately three times the previous animation. Between-deal projection preserves previous dealer, and selected next dealer may manually start when no automatic countdown blocks it. Without-three is now an atomic declaration-only command with a legal bid; no defender action can precede it. The FAQ snapshot and house rules are updated. Compact action buttons, stable discard alignment, inward speech bubbles and notebook changes are covered in PR18_TABLE_POLISH.ru.md. Full repository CI and three-client visual acceptance remain pending. No provider settings changed.

## PR19 table details candidate

Base: 2bc7f789e92bff14b3f1c0a998ad301b745b2204 (PR #290 merged). Place the deck by the playing circle between deals, replace score menu entry with clickable notebook on table, keep own avatar beside hand and move trick trains to inward edges / above own hand. Mark only global latest trick, keep public widow visible for ten seconds after receipt on opponents' clients, display the approved humorous game notices. Ranking names are resolved from bounded name-only profile queries using existing opaque player IDs; no stored result changes or UID disclosure. Declaration-only without-three authorization unchanged. See PR19_TABLE_DETAILS.ru.md. Full CI, actual layout and three-client acceptance still pending. No changes to production flags. Format and test before staging; verify clean tree before push.

## PR20 - shell and bidding refinements

- Base: `a4bc01d`; previous PR19 merged as #291.
- Replace the incomplete first PR20 installer; all transformations are preflighted before writing and restricted to the dedicated branch.
- Move game navigation into the host header, render ledger-based notebook thumbnail and three-seat local perspectives, align trick bundles with avatars, and expand bid choices inline with version-scoped special bid confirmation.
- Automatically initiate unambiguous settlement from the connected administrator client; allow declarer settlement when the authoritative projection offers a real choice. Offline automatic settlement remains a separate server lifecycle concern.
- See `docs/PR20_SHELL_AND_BIDDING.ru.md`. Full CI and three-client acceptance remain pending.

## PR21 — fixed game menu, auction priority and unanimous misere offer

- Replace collapsible game menu with permanent horizontal actions; move fullscreen beside account and reuse website branding.
- Bottom-align own avatar; separate opponent trick trains; place opponent clocks at the inward top edge.
- Fix notebook writing lanes and use an irregular oval for the target.
- Restore usable portalled settings, cyclic options and uniform card previews.
- Derive Here priority from the first bid/pass sequence; preserve 6-spades restriction and derive rights after undo.
- Ordinary misere after discard supports a private-to-participants offer, two approvals or immediate rejection. The second approval settles atomically through the existing scoring engine. No fake tricks; rejection restores normal play. Legacy GameState records decode with empty votes.
- Accept legal next-lead drops during decorative collection; no new polling or network requests.
- Candidate package: full CI, three-client visual acceptance and latency measurement remain required. Deploy frontend and backend together; do not mix old and new game clients during a vote.

## PR22 - Firestore quota incident and transport resilience (2026-11-25)

- Production Vercel environment lacked both realtime enable flags; HTTP fallback was the active transport. Preview and Production had the same Firebase project ID.
- Logs showed RESOURCE_EXHAUSTED on settings. Firestore Usage showed 54k reads / 8.2k writes over 24 hours; exact daily quota counter and attribution require provider verification.
- Preserve uncached admission/grant checks, authoritative Firestore transactions and seat-specific WebSocket projections. No change to game rules, scores or persistent state.
- Add bounded HTTP fallback, shared process-local quota cooldowns, Retry-After forwarding, and a reconciliation retry floor. Settings fail closed with an unavailable message instead of a misleading sign-in redirect on admission failure.
- Production activation is a separate configuration step; see docs/PR22_QUOTA_RECOVERY.ru.md. Do not declare the incident resolved before a measured three-client test and quota verification.
- No paid plan, credential, deployment, database, IAM or production environment changes are made by the installer.

### PR22 settings layout lint correction

- Resolve account data and owner status before constructing JSX; retain distinct unavailable and unauthenticated outcomes.
- Keep the existing settings error boundary and authorization checks.
- Run frontend lint, typecheck and full local CI before merging.
