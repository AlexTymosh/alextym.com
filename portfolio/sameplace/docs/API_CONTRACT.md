# HTTP contract — room core v1

All API operations are under `/api/sameplace`; same-origin browser adapter `/portfolio/sameplace/api/<operation>` allows only listed operations, and handles POST `session`/`signout` locally. Browser routes: root, `/rooms`, `/r/{slug}`, `/j#<token>` (preferred), `/j/{token}` compatibility. All are feature-gated. No global-site localization or root-level room links.

| Method/path suffix | Request fields | Result |
|---|---|---|
| GET `/status` | Existing SP01 project grant | Original foundation response unchanged |
| GET `/identity` | Verified credential | Own uid, creator capability, platform-owner flag, configured limits |
| GET `/rooms` | Verified credential | Bounded own accessible catalogue and creation capability |
| POST `/rooms` | `request_id`, `slug`, `name`, `capacity`, optional `interior` | Room projection |
| GET `/rooms/{slug}` | Verified credential + membership | Room projection; archived owner management only |
| POST `/rooms/{slug}/update` | `request_id`, `version`, `name`, `capacity`, `interior` | Updated room |
| POST `/rooms/{slug}/design` | `request_id`, `version`, `interior` | Updated room (designer/owner) |
| POST `/rooms/{slug}/archive` or `/restore` | `request_id`, `version` | Updated room |
| POST `/rooms/{slug}/roles` | `request_id`, `version`, `uid`, `roles` | Updated room |
| POST `/rooms/{slug}/block`, `/remove`, `/unblock` | `request_id`, `version`, `uid` | Updated room |
| POST `/rooms/{slug}/invite` | `request_id`, `version`, `target_kind` (`uid` or `email`), `target`, `days` (default 7) | Updated room + one-time `invitation_token` |
| POST `/rooms/{slug}/revoke_invite` | `request_id`, `version`, `invite_id` | Updated room |
| POST `/redeem` | `request_id`, `token` | Member projection; no new platform grant |
| POST `/rooms/{slug}/propose_transfer` | `request_id`, `version`, `uid` | Pending transfer visible to owner/target |
| POST `/rooms/{slug}/accept_transfer` | `request_id`, `version`, `transfer_id` | New owner projection |
| POST `/rooms/{slug}/cancel_transfer` | `request_id`, `version` | Updated room |
| POST `/admin/approval` | `request_id`, `uid`, `approved` | Creator approval state |
| POST `/admin/limits` | `request_id`, `storage_rooms`, `active_rooms`, `active_participants`, `capacity_ceiling` | Policy limits |

Requests are strict Pydantic models; unknown fields denied. `request_id` is a client-generated opaque ASCII 16–64 chars, not an authentication secret. Slug is lowercase ASCII 3–48 chars with no leading/trailing dash; reserved words denied on creation. IDs, schema/state and error codes are locale-independent. All command responses use HTTP 200; browser text resolves stable codes in Russian resources. `Cache-Control: no-store`, `Referrer-Policy: no-referrer`. No raw validation input is echoed. Errors: 401 AUTH_REQUIRED, 403 ACCESS_DENIED/CREATOR_REQUIRED, 404 ROOM_NOT_FOUND/INVITE_INVALID, 409 OWNER_LIMIT/SLUG_TAKEN/STALE_VERSION/REQUEST_CONFLICT/CAPACITY_LIMIT/STORAGE_LIMIT/etc., 413 oversized, 415 wrong content-type, 422 INVALID_REQUEST, 429 RATE_LIMIT, 503 STORAGE_UNAVAILABLE/IDENTITY_UNAVAILABLE. No cross-room error detail. 404 is also the disabled feature response. Transient failures must not lead to optimistic membership or blind automatic retries. A retry of a command preserves its request ID; new intentional action uses a new ID. The UI refreshes explicitly, no background polling.

Data projections are described in DOMAIN_MODEL.md and SECURITY_AND_PERMISSIONS.md. `room.capacity` is configured, not proof of real-time admission. `room.members` and invite metadata are only included for entitled management roles. No game/activity state or realtime endpoint in SP02.
