# Security and permissions — SP02

## Trust boundaries

The original SP01 `/api/sameplace/status` remains protected by the existing project grant. Room Core has a separate composition dependency `require_sameplace_identity`: exact server feature flags first, verified Firebase ID token or Firebase session cookie, provider and admission checks. An explicitly denied/revoked/expired Lab record is never bypassed. A new account with no Lab record must have a verified email and a supported sign-in provider (OAuth also requires a current bound provider subject). Only the configured, verified platform Owner UID receives platform authority; never accept role, UID, email, or owner from a client body. Admitted accounts keep the existing password/OAuth policy; only verified email claims can satisfy email-targeted invitations. Authentication alone does not allow any room access. No Lab record, generic grant, or project Test/Admin permission is minted by SamePlace.

The public route shell is feature-gated, noindex/nofollow, contains no private metadata. The client authenticates with the existing Firebase configuration and in-memory SDK. The project-local BFF creates a scoped HttpOnly, SameSite=Strict session cookie only after recent verified ID token and backend identity proof. It may use the existing host cookie when no local cookie is present. Explicit SamePlace logout writes a signed-out marker that suppresses this fallback; it does not log out the host website. Existing host logout does not clear a separate SamePlace session; users can sign out of SamePlace explicitly. All browser mutations require configured same origin and JSON size <=16 KiB. Backend validates the credential independently; it never trusts frontend authentication or cookies automatically. No arbitrary proxy path, redirects, query parameters or client-supplied authorization forwarding. Direct backend accepts only the explicit signed credential, not ambient browser cookies. No direct browser Firestore access; existing deny-all rules unchanged.

New registration is existing Firebase email/password + explicit verification email or Google sign-in. No automatic invite emails/SMS; only personal copying of the link. Existing accounts can use host sign-in (including other existing host providers) and host cookie fallback. No change to shared login, global locale, Firebase identity/grant rules, or other project routes.

## Permissions (server enforced)

| Action | Required authority |
|---|---|
| View own identity / room catalogue | Verified identity; only current own memberships returned |
| Create room | Owner or explicit creator approval, active count <3, storage/slug/capacity constraints |
| View room | Active membership, active room; archived metadata only for room owner for management |
| Rename/capacity/archive/restore | Room owner; restore additionally approval and capacity/count check |
| Change interior preset | Room owner or designer |
| Invite/revoke invitation | Owner or inviter capability; delegate may revoke own invitation |
| Assign/revoke room roles | Room owner only; cannot modify owner's role or escalate self |
| Block/remove/unblock | Owner or moderator; moderator cannot target owner, self, or privileged member |
| Propose/cancel/accept ownership transfer | Current owner proposes/cancels; specifically approved target active member accepts; both counters updated transactionally |
| Global creator approvals/limits | Verified platform Owner only; no implicit private room access |

No global owner bypass of room object permissions. Roles DJ and organizer are stored but have no media/game powers until their modules implement and test them. The game master is future activity-scoped, not a room role. Unknown members/slugs and inaccessible rooms return indistinguishable neutral 404. No secret invitation target/digest or other-room metadata in guest projections. Privileged room membership management may see stable UID and roles, never raw email/phone. New invitations are target-bound to UID or a verified email digest, default 7 days, 1–30 days, 256-bit random secret. Backend receives plaintext only in bounded POST JSON. Prefer `/portfolio/sameplace/j#<token>` in generated links: fragments are not transmitted in HTTP request paths and reduce proxy/access-log exposure; the originally specified `/j/<token>` remains a compatibility route, no-referrer, no analytics, and should not be used for real links until provider logs have been reviewed. Fragment change is an implementation safety decision, not a change to the permanent room slug. Invite issued by a removed inviter or one whose capability was revoked is invalidated permanently. Revocation of member blocks old invitations even after unblocking. Archive invalidates pending invitations. Explicit membership revocation denies the next REST request; no websocket exists yet. SP03 must invalidate tickets/leases and clear cached projections on live revocation.

## Limits and operational gates

No polling, scheduled billing, provider change or production activation in SP02. Process-local mutation limiter: 30 per UID and 180 total per minute, bounded map; quota circuit opens for 120s on confirmed ResourceExhausted. Not a global usage meter, not a hard cost guarantee, no durable distributed rate limiter. Failed storage/identity calls fail closed and return neutral 503 (Retry-After where available). Before enabling real traffic, verify isolated Firebase environments, email verification quotas, actual WAF/rate controls and provider path/body logging, scoped session cookie, OAuth binding and separate Lab denial. Capacity and active limits must be enforced in SP03 and reduced to measured free AV capacity in SP07. No public rooms or automatic admission by friendship.
