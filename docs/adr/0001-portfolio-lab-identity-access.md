# ADR-0001: Portfolio Lab identity and access boundaries

- **Status:** Accepted design direction; not yet implemented
- **Date:** 2026-11-12
- **Specification:** [Portfolio Lab TRS v1.0](../specifications/portfolio-lab-auth-access.md)

## Context

The product uses one Next.js deployment (Vercel), one FastAPI deployment (Render), and embedded project modules under `portfolio/<project_id>/`. Fleet VOR Hub currently authenticates with a project password and persists disposable demo data in SQLite. The new Portfolio Lab must give selected visitors different permissions on different projects without changing the public RAG, Resume, Contact, or Telegram features.

A frontend route guard cannot secure `/api/*`: Next.js rewrites these paths to Render, and Render is directly addressable. An HTTP `Origin` header is not proof of authentication or authorization.

## Decision

1. **Identity:** Use Firebase Authentication (Google, Microsoft, GitHub, and email/password). An authenticated identity receives **no project access by default**.
2. **Durable control plane:** Firestore stores access grants, identity associations, policies, audit events, and durable outbound-email quota state. The Git-controlled `portfolio/catalog/registry.json` and each `project.json` remain the canonical catalogue, not Firestore.
3. **Authorization:** Project-scoped `No Access`, `View`, `Test`, and `Admin`; global `Owner` authority pinned to a trusted Firebase UID. Project `Admin` cannot manage central access grants or security policy.
4. **Capabilities:** `View` is read-only. `Test` and `Admin` may change demo data and perform real external actions, including email delivery, within Owner-managed quotas and abuse protections. Only `Admin` and `Owner` may reset demo data.
5. **Invitations:** Owner provisions accounts and grants, may set an initial password valid for up to 90 days or issue a link for self-setting a password, and explicitly chooses whether to send an invitation. No separate mandatory email-verification step, but untrusted OAuth email claims are insufficient to claim an invitation.
6. **Identity linking:** Users may link providers with different emails only after proof of control of the trusted existing account and the additional provider; never auto-merge Firebase UIDs based on email.
7. **Project ownership:** Shared identity and policy are thin platform services. Each project owns its frontend, API, business logic, data store, seed/reset, and migrations. Cross-project imports and mutations are forbidden. Users testing the same project share its demo environment.
8. **Persistence:** Fleet retains SQLite. Loss of demo mutations after Render restart/redeploy is acceptable. Identity, grants, quotas and security policy must not rely on Fleet SQLite.
9. **Deployment:** Remain on Vercel and Render, with no new paid dependency. Keep Fleet's legacy authentication until a controlled migration, then remove it as an alternative authorization path. No simultaneous fallback password bypass.
10. **Default deny:** Each protected Next.js action and each protected FastAPI endpoint must check identity and a current project grant. Direct Render API requests must not circumvent the policy. If the authorization store is unavailable, protected actions fail closed.

## Trust boundaries

| Crossing | Enforcement |
| --- | --- |
| OAuth provider → platform | Verify token and trusted UID; do not trust a free-form email claim |
| Browser → Next.js | Server-validated session, secure cookie handling and CSRF/Origin controls |
| Browser or rewrite → FastAPI | Independently validate credentials, grant, project ID and capability; test direct Render requests |
| Platform → project | Narrow, explicit authorization contract; no project import of host business internals |
| Project A → project B | Separate owned data and modules; no cross-project internal imports or resets |
| Test/Admin → real email | Owner-configured quota, durable atomic reservation, audit, idempotency and provider safeguards |
| Render lifecycle → control plane | No loss of grants/policies/quotas due to disposable demo SQLite |

## Integration gates deliberately deferred

The following require working integration tests in later PRs, rather than assumptions in this ADR:

- Prove a credential/session transport accepted by both Next.js and FastAPI **even for direct Render access**. A Vercel-origin HttpOnly cookie is not automatically a Render-origin credential.
- Decide grant caching, revocation propagation, exact Firestore document schemas, transaction semantics and index requirements.
- Ensure initial-password expiry cannot be bypassed by authenticating with the password and then exchanging credentials for another session.
- Test safe multi-provider account linking and recovery with live providers, including corporate Microsoft policies.
- Test durable quota reservation, concurrent sends, repeat requests and ambiguous provider outcomes before enabling flexible recipients.

## Alternatives and consequences

- **Shared Fleet password:** rejected; cannot represent per-user project grants or targeted revocation.
- **PostgreSQL migration:** rejected for this task; demo writes do not require durable storage.
- **Firestore for all project data:** rejected; storage remains project-owned.
- **Per-project microservices:** deferred; added cost and operational overhead without a demonstrated need.
- **Frontend-only access control:** rejected; direct Render hostname remains reachable.

Logical module separation does not guarantee runtime CPU/memory isolation in a shared FastAPI process. Firebase and Firestore introduce external availability and credential-lifecycle complexity; public site functions must remain independent where possible.

## Implementation and acceptance

See [SESSION_NOTES.md](../../SESSION_NOTES.md) for six sequential PRs. Foundation PR #243 adds this ADR and read-only security/ownership baselines without changing existing Fleet behavior. Every PR requires `task ci`, hosted GitHub CI and focused security regression checks. The full technical specification remains authoritative for product requirements.
