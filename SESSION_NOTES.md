# Session Notes

## Issue #107: preserve owner messages after handoff

Branch: `codex/107-owner-chat-context`.

The user approved three commits, committed Step 1 as `68434d4` and Step 2 as
`d98b999`, and authorized Step 3. Step 3 is implemented and awaits user review and
a user-created commit. Verification results and dependency audit follow-ups are below.
Do not commit, push, or close the issue on their behalf.

### Step 1 completed: backend contract and context

- Accept `owner` alongside `user` and `assistant` in chat history and handoff transcripts.
- Preserve speaker identity in contextualization, answer prompts, temporary sessions,
  and Telegram transcript text. Owner messages remain untrusted context, not facts or instructions.
- Resolve ambiguous references to owner replies; ask for clarification when unresolved.
- Prevent owner replies and handoff-close/expiry notices from confirming an old handoff offer.
- Add regression tests and update API, RAG, and security documentation.
- `task backend:check`: passed, 509 tests. One earlier run had an intermittent failure in
  the existing Redis probe timeout test (`SET`); the complete rerun passed without Redis changes.
- Existing Starlette/httpx deprecation warning remains. Tests used local provider doubles;
  live OpenAI, Qdrant, Telegram, and browser end-to-end behaviour were not verified.

### Step 2 completed: frontend history and transcript

- Map visible `alex` replies to API `owner` entries in AI history and repeat-handoff
  transcripts. Keep UI sender labels and the live handoff SSE role unchanged.
- Include owner messages in the existing count, per-message, and total character limits.
- Add 14 pure history/transcript checks to the existing Playwright runner, covering
  speaker order, unchanged UI data, ordinary chat, blank text, clipping, and newest-message limits.
- Update API, architecture, and RAG documentation to describe frontend transmission.
- Synced local dependencies with the existing lockfile before final verification.
- `npm run lint`, `npm run typecheck`, and `npm run build`: passed with Next.js 16.3.4.
- Focused `chat-history.spec.ts` checks: 14 passed using the Chromium project and one worker.
  These tests exercise pure functions, not a browser conversation or live providers.
- The initial focused run finished its tests but stalled while stopping the managed Next.js
  server on Windows. It was interrupted; its server process is no longer running. The successful
  rerun set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000` to skip the unnecessary managed server;
  these pure tests make no requests to that URL.
- `git diff --check` and the repository raw-Cyrillic check passed.
- Full browser scenarios and repository-wide CI remain part of Step 3.

### Step 3 completed: browser regressions and final checks

- Add seven browser scenarios, run on desktop and mobile Chromium (14 checks):
  manual close, SSE close, and session expiry, each through streaming and JSON
  fallback, plus a second handoff session with a distinct session ID and owner reply.
- Assert actual outgoing history/transcript payloads, speaker order, preserved owner
  labels, explicit repeat-handoff consent, and return to AI routing after closure.
- Update API testing documentation with regression coverage and mock boundaries.
- Focused browser run: 14 passed. The initial attempt could not launch browsers
  because the Chromium revision required by the installed Playwright was missing.
  Installed the required browser; the successful run used elevated execution to
  avoid the previously observed Windows sandbox server-teardown hang.
- Full `task ci` passed repository hygiene, project config, setup wizard,
  deployment config, frontend checks, and free RAG checks. Frontend lint, typecheck,
  resume parser, production build, and all 122 Playwright checks passed. Free RAG
  validation passed four generated-case tests and all 27 contract-evaluation cases.
- The first backend run had 508 passes and the same existing intermittent Redis
  probe timeout failure (`test_hung_operation_times_out_without_hanging_cleanup[SET]`).
  A complete `task backend:check` rerun passed all 509 tests without code changes.
- The initial `task ci` did not finish green because of that intermittent backend
  failure and an unavailable Docker Engine. After the user started Docker,
  `task docker:build` passed on 2026-09-30 and produced `alextym-backend:latest`.
  All CI components have now passed, with backend and Docker verified separately
  after the initial full run; the entire pipeline was not rerun.
- `npm audit --json` confirmed two affected package groups (one high, one critical).
  `npm audit --omit=dev --json` reports only Next.js. Dependencies and lockfiles
  were not changed in this branch; remediation is outside issue #107.
- Next.js 16.3.4 is covered by [GHSA-vcvr-r3jv-pc5j](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j),
  fixed in 16.3.6. The reported RCE requires attacker-controlled SVG input to the
  Node.js `next/og` ImageResponse implementation. No such usage was found in the
  project; its Open Graph image is the static `frontend/public/og-image.png`.
- `brace-expansion` 1.1.18 and 5.0.9 arrive through ESLint/minimatch tooling.
  Audit reports two stack-exhaustion advisories and one CPU-exhaustion advisory
  (GHSA-6j4f-fj2g-mc7p, GHSA-qhr7-859c-m2p7, GHSA-q2hr-2g5m-vwhr).
  Updating the respective dependency lines to at least 1.1.21 and 5.0.12 addresses
  these three advisories. They are absent from the production-only audit.
- The existing Starlette/httpx deprecation warning remains. The dependency audit
  is not a comprehensive security assessment of the application or Docker image.
- Browser tests use mocked API responses; backend tests use provider doubles.
  Live Telegram delivery, Qdrant retrieval, and model behaviour remain unverified.
  No ingestion or external messages were sent.
- Removed the unrelated generated `next-env.d.ts` change from the production build.

### Review boundary

The three implementation steps for issue #107 are ready for review. Step 3 changes
only browser tests, API testing documentation, and these notes. The user requested
a readiness assessment, PR text, and squash-commit text, and will create the third
commit, push, and open the PR after review. No commit, push, PR creation, deployment,
or GitHub issue closure has been performed by the assistant.
