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


## SP03 additive endpoints

API prefix `/api/sameplace`, browser BFF `/portfolio/sameplace/api`. All HTTP mutations use POST, strict JSON/body bound, same-origin cookie BFF, verified identity and server object policy. No arbitrary proxy or query string. Read-only history cursor uses POST `/chat/page` solely because the existing BFF denies query strings. Durable commands include `request_id` as in SP02; no version is needed for independent additive social records, while room core updates still use room version. Transaction receipts reject reused keys with different payloads. `ticket`, `chat/page`, `chat/cleanup` are bounded non-idempotency-receipt operations. Private results no-store.

| Method / path | Request / result | Authority |
|---|---|---|
| GET `/social/me` | Public own profile, privacy, friend projections, favourites/recent IDs, inbox | Scoped identity / existing profile |
| POST `/social/profile` | request_id, nickname, avatar enum, 8 booleans privacy -> own safe profile | Scoped identity |
| POST `/social/friend` | request_id, target public ID, request/accept/decline/cancel/remove/block/unblock -> status | Bilateral state and target binding |
| POST `/social/read_notice` | request_id, notice_id -> ok | Own inbox |
| POST `/rooms/{slug}/favourite` | request_id, enabled -> enabled | Active membership |
| GET `/rooms/{slug}/chat` | latest <=50 visible messages + before cursor | Active membership |
| POST `/rooms/{slug}/chat/page` | before (opaque message ID) -> previous visible page | Active membership |
| POST `/rooms/{slug}/chat/send` | request_id, text (1–1000) -> opaque message ID | Admitted current member |
| POST `/rooms/{slug}/chat/hide` | request_id, message_id, reason -> ok | Author or moderator with reason |
| POST `/rooms/{slug}/chat/cleanup` | empty object -> removed count | Moderator/room owner |
| GET `/rooms/{slug}/recipients` | Current members other than self, public profiles, consent-allowed channels | Active membership, no contact disclosure |
| POST `/rooms/{slug}/ping` | request_id, 1–10 public recipient IDs, internal/email/sms, text -> queued/disabled | Admitted sender, all targets current members, friendship/block/opt-in, durable rate limit |
| POST `/rooms/{slug}/ticket` | origin -> ticket, protocol_version (BFF adds ws_url) | Active member and explicit single-worker/origin policy |
| POST `/rooms/{slug}/location/propose` | request_id, lounge/table, visit/watch/play, 1–9 recipient public IDs -> proposal id | Admitted organizer/owner |
| POST `/rooms/{slug}/location/answer` | request_id, proposal_id, accept -> status | Admitted exact recipient |
| POST `/rooms/{slug}/location/cancel` | request_id, proposal_id -> ok | Admitted issuer |
| POST `/rooms/{slug}/location/move` | request_id, lounge/table -> ok | Admitted member, no active game yet |
| WS `/realtime` | auth ticket then ping only; viewer-specific snapshot / pong / machine error | Exact origin, fresh verified identity, room admission, periodic reauth |

Additional machine errors: WAIT_CAPACITY, OTHER_MEETING, TAB_LIMIT, REALTIME_BUSY, REALTIME_DISABLED, RETRY_REALTIME, TICKET_INVALID, REALTIME_REVOKED, JOIN_MEETING_REQUIRED, PROFILE_NOT_FOUND, FRIEND_STATE, FRIEND_LIMIT, NOTIFICATION_CONSENT, INBOX_LIMIT, CHAT_LIMIT, CURSOR_EXPIRED, MESSAGE_NOT_FOUND, PROPOSAL_INVALID/PROPOSAL_LIMIT. No raw request, credential, private UID or provider exception returned. See REALTIME_AND_MEDIA for full envelope and recovery. No production activation.

## SP04 decor endpoints (under `/api/sameplace`)

| Method / path | Body / result | Permission |
|---|---|---|
| GET `/rooms/{slug}/decor` | private scene/music projection, catalogue and caller's own template library | Active member |
| POST `/rooms/{slug}/decor/publish` | request_id, location, revision, room_version, scene -> fresh projection | Owner/designer |
| POST `/rooms/{slug}/decor/save_template` | request_id, name, scene, optional template_id, revision -> fresh projection | Owner/designer |
| POST `/rooms/{slug}/decor/delete_template` | request_id, template_id, revision -> fresh projection | Owner/designer and own library |
| POST `/rooms/{slug}/decor/music` | request_id, scope, revision, action, optional source_id / position_ms -> fresh projection | Owner/DJ |

All operations follow existing private response, request size, identity, rate and quota rules. Room revision notification fences successful scene/music commands. Command receipts are reused; duplicate command cannot repeat a durable mutation. Errors SCENE_CONFLICT, MUSIC_CONFLICT, SOURCE_UNAVAILABLE, INVALID_SEEK, TEMPLATE_LIMIT. No raw arbitrary URL permitted. Scene registry IDs and machine errors are language independent.

## SP05 media extension (existing WebSocket)

No new HTTP operations, BFF allowlist or browser credentials. Existing `/api/sameplace/realtime` auth remains mandatory. Media state and addressed signaling are feature-gated, with strict payload bounds. `media.join`, `media.leave`, `media.tracks`, `media.signal`, `media.mode`, `media.mute` commands; `media.state`, `media.signal`, `media.error`, `media.disabled` server frames. Current room/channel/pair and active connection checked on each signal. Owner/organizer/moderator mode and Owner/moderator mute use fresh verified room permissions; no remote unmute. Stable MEDIA_* codes, never echo SDP/ICE/credentials in error. See REALTIME_AND_MEDIA for detailed protocol. No persistence or video proxy.
