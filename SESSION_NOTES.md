# Current project handoff — Portfolio Lab identity and access

**Updated:** 2026-11-12  
**Status:** Foundation PR #243 is in progress. No Firebase or new access system is deployed; six-PR plan remains in force.
**Current PR:** [#243](https://github.com/AlexTymosh/alextym.com/pull/243), branch `feat/portfolio-lab-foundation` (draft until all acceptance checks pass).

## Authoritative documents

- [Portfolio Lab technical requirements](docs/specifications/portfolio-lab-auth-access.md) — `PL-IDENTITY-ACCESS-TRS-001`, version 1.0; authoritative statement of product requirements, edge cases, and acceptance criteria.
- [Existing portfolio architecture](docs/architecture/portfolio.md) — current host/project ownership and compatibility invariants. **Add a link to the technical requirements and document the resulting identity/authorization boundaries during PR 1**, not as an unreviewed architecture change in this documentation handoff.
- [Fleet VOR Hub project manifest](portfolio/fleet_hub/project.json) and [project registry](portfolio/catalog/registry.json) — stable project IDs and demo routes.
- [Fleet VOR Hub README](portfolio/fleet_hub/README.md) — existing implementation and SQLite invariants.
- [CI workflow](.github/workflows/ci.yml) and [Taskfile](Taskfile.yml) — project, backend, frontend, RAG, and Docker gates.

> **Before coding:** Re-read the technical requirements and inspect the latest `main`. Existing architecture documentation contains historical branch/PR status that must not be treated as current proof of deployment. Check that the technical requirements file exists locally; it is supplied separately and is **not** part of this documentation patch.

## 1. Agreed product decisions

1. **Identity:** Firebase Authentication with Google, Microsoft, GitHub, and email/password.
2. **Admission:** Owner provisions invitations/users; a successful external-provider login alone never grants access to private projects.
3. **Account provisioning:** Owner can choose an initial password or issue/copy a link that lets the recipient set a password. Notifications are optional, never sent merely because a grant is saved.
4. **Initial password:** Not one-time; an application-enforced validity of up to 90 days, independent of the grant and account lifetime. This is not a native Firebase password-expiry feature.
5. **Email:** No separate mandatory email-verification step. Nevertheless, do not trust an unverified/attacker-controlled provider email as proof that an invitation belongs to its holder. Onboarding and account linking must prove ownership securely.
6. **Account linking:** One person may link several providers with different email addresses to one trusted Firebase UID. Never automatically merge two existing Firebase users based on email text alone.
7. **Roles:** `No Access`, `View`, `Test`, and `Admin` are assigned per project. `Owner` is a separate global authority pinned to a Firebase UID; project `Admin` cannot manage central grants or identity/security settings.
8. **Capabilities:** `View` is read-only. `Test` can mutate demo data and perform real external actions, including live email. `Admin` also manages that project's demo data/domain settings and can reset its demo; Owner controls central policies and quotas.
9. **External-action policy:** Per-project Owner-managed switches, recipient-count quotas, and audit. Test/Admin can send to valid addresses within the allowed quantity limits; the target UX has no recipient-domain allowlist by default. Anti-abuse controls, server authorization, idempotency, and provider limits remain mandatory.
10. **Project isolation:** Each project's logic, API, data, and demo reset are independent. Testers of the **same** project share its demo environment, but cannot alter another project's data or permissions.
11. **Fleet storage:** Keep SQLite, seed, migrations, and domain behavior. Loss of test mutations after Render sleep/restart/redeploy is acceptable. Do **not** move Fleet data to PostgreSQL or Firestore for this initiative.
12. **Control-plane durability:** Use Firestore for users/grants, security policies, audit records, and live-email quota state; this data must survive Render restarts. The repository's `portfolio/catalog/registry.json` and per-project manifests remain the canonical list of projects; Firestore is not a second manually maintained project catalogue.
13. **Hosting:** Keep Next.js on Vercel and FastAPI on Render. Entry/login and eligible-project catalogue should work without waking Render. Preserve existing public chat/RAG, resume, contact, Telegram, and related features.
14. **Security:** All protected Next.js pages and **every protected FastAPI route** require valid identity and adequate project capability, including direct requests to the Render hostname. No parallel legacy Fleet password bypass after cutover.
15. **Free-tier goal:** No new paid infrastructure without Owner approval. Existing Render warm-up/ping may stay as a convenience, never as a security or availability dependency.

## 2. Verified repository baseline and hazards

- `backend/app/main.py` mounts the Fleet router in the shared FastAPI host; optional Fleet bootstrap must not take down unrelated site functionality.
- `frontend/next.config.mjs` rewrites `/api/:path*` to the Render origin. A Next.js route guard alone **cannot** protect the backend.
- Fleet currently includes password-based login/session routes and a dedicated session cookie. Record every Fleet endpoint, method, status, cookie, origin rule, and security dependency before changing it.
- Fleet's SQLite lifecycle is self-contained. The immutable seed, migration behavior, and regression suite must remain intact.
- Fleet email delivery already implements Resend integration, recipient policy, limits, and request-id-based deduplication. Audit exact current behavior before changing the policy; the existing SQLite journal cannot be the sole durable ledger for global email quotas.
- The existing project registry contains `fleet_hub`; architecture checking has Fleet-specific paths. Generalize checks to **all** registered projects without creating a speculative plugin framework.
- Current GitHub CI has five jobs: `project`, `backend`, `frontend`, `rag`, and `docker`. Preserve all five.

## 3. Delivery strategy: six sequential PRs, approximately 18 working commits

The six-PR target balances reviewability and integration risk; commit counts are planning estimates, not quotas. Develop **one functional PR at a time** from a refreshed `main`; merge only after local and hosted CI checks. Prefer squash merges (approximately six resulting commits on `main`).

| PR | Branch | Planned working commits | Risk | Release gate |
|---|---|---:|---|---|
| 1 — Foundation | `feat/portfolio-lab-foundation` | 2 | Low | Specification/ADR and baselines reviewed; `task ci` |
| 2 — Firebase Identity | `feat/portfolio-firebase-identity` | 4 | High | Four sign-in methods, linking and sessions tested |
| 3 — Authorization | `feat/portfolio-project-rbac` | 3 | High | Direct Render access and revocation fail closed |
| 4 — Owner Console | `feat/portfolio-access-console` | 3 | Medium–high | Owner-only invitation/grant/policy UI verified |
| 5 — Fleet Integration | `feat/fleet-firebase-authorization` | 3 | High | Fleet golden-path/SQLite regressions pass |
| 6 — External Actions & Release | `feat/portfolio-external-actions-release` | 3 | High | Durable quota/idempotency and production smoke pass |

### PR 1 — Architecture and security foundation (2 commits)

**Scope**

- Add the technical specification to the tracked project documentation and link it from the root README (these files may already be placed by the Owner before coding).
- Add ADR(s) and link the requirements from the relevant section of `docs/architecture/portfolio.md` **during implementation**; distinguish agreed requirements from proposed SDK and data-model decisions.
- Define identity, grant, capability, project registry, external-action and session contracts; threat model direct Render origin, identity confusion and account-linking collisions.
- Capture current Fleet route/method/auth/cookie/Origin/status baselines; create deterministic tests and emulator configuration scaffolding with no production behavioral changes.
- Generalize existing registry/import/frontend-boundary checks to all registered portfolio modules; retain the current Fleet contract.

**Suggested commits**

```text
📝 docs(auth): define portfolio identity and access architecture
🧪 test(portfolio): add security baselines and project boundary checks
```

**Acceptance:** No public behavior changes; `task ci`, GitHub CI, legacy Fleet tests and project boundary checks pass.

### PR 2 — Firebase identity and session lifecycle (4 commits)

**Scope**

- Configure Firebase Auth providers Google, Microsoft, GitHub, email/password; use separate safe development/test config.
- Owner-provisioned accounts and setup-link flows; application-enforced initial-password expiry (1–90 days) that does not expire a grant.
- Secure UID-preserving provider linking, including different emails, conflict/recovery paths and untrusted provider email handling; no automatic UID merging.
- Issue/validate secure server sessions; implement login/logout and CSRF/Origin rules. Prove identity continuity across Vercel and direct Render access without disrupting public `/api/*` and SSE.
- Keep Portfolio Lab feature-disabled in production while backend authorization is incomplete.

**Suggested commits**

```text
🔐 feat(auth): integrate Firebase providers and sessions
🛡️ feat(auth): enforce invited-user admission and secure cookies
🔑 feat(auth): implement initial password lifecycle
🔗 feat(auth): support secure provider linking and recovery
```

**Gate:** Firebase emulator tests and real provider smoke; direct-origin and session threat checks. **Do not proceed to PR 3 until the cross-host session design is proven.**

### PR 3 — Authorization and Firestore control plane (3 commits)

**Scope**

- Durable Firestore repositories for Owner, user/UID mapping, grants, invitation states, external-action policies, audit records, and supporting security metadata.
- Central authorization policy and project-scoped capability checks; default deny; immediate/defined-bound revocation and grant expiry.
- Enforce protected API authorization independently inside FastAPI. Preserve public routes including RAG/chat/contact; fail closed if security state is unavailable.
- Negative tests for direct Render calls, missing role, cross-project access, revoked sessions, forged identity, and inaccessible projects.

**Suggested commits**

```text
🗄️ feat(authz): add durable Firestore access repositories
🛡️ feat(authz): enforce project-scoped capabilities
🧪 test(authz): cover revocation and API bypass attempts
```

**Gate:** No protected endpoint is accessible with invalid/ungranted identity, including via direct Render hostname.

### PR 4 — Owner administration and invitations (3 commits)

**Scope**

- Owner-only dashboard for user provisioning, initial password and setup-link options, project grants, role changes, expiry, revocation and audit.
- Dynamic project selections derived from canonical project registry/manifest data; newly registered projects grant no non-Owner permissions.
- Per-project external-action settings and quota controls. Saving a user/grant must **not** send mail; a distinct explicit action sends an invitation through Resend or copies a link.
- Validate authorization, anti-CSRF, safe password handling, lack of secret exposure, and non-Owner denial.

**Suggested commits**

```text
👤 feat(admin): implement Owner-managed invitations and grants
🧭 feat(admin): build project access management console
✉️ feat(admin): add optional notifications and policy settings
```

**Gate:** Owner can provision/manage a user end-to-end; project Admin cannot manage global identities, grants or security policies. New external-action controls remain inactive until the durable sending mechanism is deployed.

### PR 5 — Fleet authorization integration (3 commits)

**Scope**

- Classify Fleet endpoints as `View`, `Test`, or `Admin` (with explicit privileged action exceptions) and preserve their existing public paths.
- Replace legacy password-session dependencies with project-aware authorization behind a controlled rollout flag. Never treat the legacy password as a parallel way to bypass the new RBAC mode.
- Preserve Fleet domain rules, SQLite runtime/seed/migrations, exports, Origin policy, frontend behavior and tests; leave non-Fleet services unchanged.

**Suggested commits**

```text
🚚 refactor(fleet): classify endpoint capabilities
🔒 feat(fleet): integrate project-scoped authorization
🧪 test(fleet): preserve routes and SQLite regressions
```

**Gate:** Fleet golden paths, project-role checks, negative direct-origin tests and SQLite integrity tests all pass. Production auth remains on the explicitly selected known-good mode until the final cutover.

### PR 6 — Durable external actions and production rollout (3 commits)

**Scope**

- Enable owner-configurable project live actions for Test/Admin; enforce recipient-quantity quotas with durable Firestore reservation/accounting, plus provider-level limits and abuse safeguards.
- Migrate the Fleet email policy from environment-only recipient restrictions to the agreed recipient-flexible, quota-limited project policy; preserve idempotency and handle ambiguous provider outcomes conservatively.
- Complete the controlled Fleet auth cutover and remove/disable legacy login/session bypasses; validate direct Render routes and cross-project isolation.
- Execute end-to-end smoke for OAuth/password, expired initial password, role changes, linking, Revocation, live email, quota concurrent requests, Render sleep/reset and public RAG stability.
- Finalize operations runbooks, monitoring, docs, recovery and rollback procedure.

**Suggested commits**

```text
✉️ feat(email): add durable project quotas and idempotency
🚦 feat(auth): complete Fleet authorization cutover
✅ test(release): add production verification and recovery checks
```

**Gate:** `task ci`, GitHub CI, safe live-provider smoke, durable-quota concurrent/restart tests, explicit Owner-approved rollout and a tested safe disable/rollback. Never reactivate the legacy password as a production bypass.

## 4. Cross-PR quality and security rules

- **Before any implementation:** Update `main`; check Git worktree, existing open PRs and real deployment state; capture baseline `task ci` results.
- **Per PR:** Keep the diff focused; prefer roughly 300–600 changed business-code lines when feasible, but do not split a security invariant merely to satisfy a line count. Commits represent complete, reviewable units.
- **Local gates:** `task ci` and relevant focused tests before push; `git diff --check` after edits.
- **GitHub gates:** Verify all existing five CI jobs; do not mark unrun checks as passing.
- **Security gates:** Never trust client-only authorization. Every protected request must verify identity, active grant, project scope, capability, and any external-action policy. Guard direct Render access. Recheck expiry/revocation according to documented policy; fail closed.
- **Project separation:** No cross-project internal imports or shared mutable demo data. Cache keys and rate budgets are project-scoped. Modular monolith is logical isolation, not process-level resource isolation.
- **Credentials:** No secrets, plaintext passwords, action links, tokens or service-account JSON in Git or logs. Use secure Vercel/Render environment variables. Bootstrap Owner only through a protected explicit operation with a pinned Firebase UID.
- **Email:** Routine CI never sends live emails. Use sandbox/test addresses for integration. Idempotent retries must not duplicate provider sends; preserve unknown-outcome reconciliation. Quotas must survive disposable Fleet SQLite resets.
- **Deployment:** Do not expose private Lab navigation or protected Fleet endpoints until server-side authorization is active. Keep feature flags fail-closed and avoid a security-weakening rollback path.
- **Compatibility:** Preserve public Resume/Chat/RAG/SSE/Contact/Telegram flows, Fleet routes, seed and SQLite behavior. Keep no-cost hosting unless explicitly approved otherwise.

## 5. External setup and dependencies

| Item | Needed by | Status |
|---|---|---|
| Firebase plugin connected and real capabilities inspected | PR 2 | To verify; do not assume connected |
| Firebase Auth project, dev/test environments and supported provider callbacks | PR 2 | To configure |
| Firebase UID for Owner; emergency recovery plan | PR 2–3 | Requires secure Owner action |
| Firestore locked rules, Admin SDK credentials, environment secrets | PR 3 | To configure |
| Real Google, Microsoft and GitHub test accounts | PR 2 | To verify provider policies |
| Verified Resend sender, invited-user templates and provider quotas | PR 4/6 | To verify |
| Render wake-up handling, Vercel route behavior and production smoke | PR 2/6 | To test |

## 6. Standard PR description

```markdown
## Summary

Implement [narrow Portfolio Lab phase] without changing unrelated public functionality.

## Changes

- [Describe concrete code and contract changes]
- [Describe security and compatibility changes]
- [Describe documentation and release implications]

## Testing

- [ ] task ci
- [ ] Relevant focused tests
- [ ] GitHub CI passed
- [ ] Production smoke (if applicable)

## Risks & Rollback

- Risks: [specific risks]
- Safe rollback/disable: [specific tested procedure]
```

Mark `- [x] task ci` only when that command actually passed. For squash merge, use the PR title as the single main-branch history entry. Do not claim PRs, tests, installations or deployments exist until confirmed.

## 7. Immediate next actions / handoff checkpoint

1. Continue existing draft PR #243 on branch `feat/portfolio-lab-foundation`; do not create another foundation branch.
2. Ensure `docs/specifications/portfolio-lab-auth-access.md` exists in the working tree and matches version 1.0; do not overwrite the Owner's saved copy.
3. Add this `SESSION_NOTES.md` and a root README link to the technical requirements; review the diff. This documentation handoff should be the **first** planned docs commit of PR 1, not a seventh PR.
4. During PR 1, add the requirements link to `docs/architecture/portfolio.md`, add ADR and security/contract baselines, and generalize project boundary checks.
5. Verify ADR, generic import/ownership guards, Fleet legacy access tests; run `task ci`, confirm all five GitHub CI jobs and update PR #243 before marking it ready for review. Do not merge before verification.

**Next implementation branch after PR 1 is merged:** `feat/portfolio-firebase-identity`.
