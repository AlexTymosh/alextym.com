# Realtime room shell and future media boundary

Status: SP03 candidate. WebRTC, radio, activity state and video are not implemented in this stage. See the canonical Russian requirements and [ADR 0004](adr/0004-single-worker-realtime.md). No provider is activated or billed.

## Runtime ownership

`social/composition.py` owns the project-local `Hub`, shared `QuotaCircuit`, write limiter and composition of the existing Room Core and new social routers. The FastAPI host still mounts the same public factory. Its existing `require_sameplace_identity` and `sameplace_database` adapters are injected; no host or legacy imports in project code. The BFF issues a short ticket from the scoped cookie and adds only the validated backend socket URL. The browser never receives the Firebase credential. A direct client must prove the same identity and room membership.

```mermaid
sequenceDiagram
  participant B as Browser
  participant N as SamePlace BFF
  participant A as SamePlace HTTP/WS
  participant D as Firebase Admin / Firestore
  participant H as Hub
  B->>N: POST rooms/slug/ticket (origin)
  N->>A: Scoped verified credential
  A->>D: Verify identity and active membership
  A->>H: Issue one-use ticket (25 s)
  N-->>B: ticket + ws_url
  B->>A: WSS /api/sameplace/realtime (exact Origin)
  B->>A: auth frame, ticket only
  A->>H: Consume ticket + capture epoch
  A->>D: Fresh identity/room/policy/profile
  A->>H: Atomic admission (epoch fence)
  A->>D: Record recent visit only if changed
  A-->>B: viewer-scoped room snapshot
  loop Connected
    B->>A: ping every 25 s
    A-->>B: pong (memory only)
    A->>D: reauthorize every 60 s
  end
```

## Environment contract and activation

All flags are off by default. Keep production off until SP10 and explicit approval. Local isolated verification may set `PORTFOLIO_LAB_ENABLED=true`, `SAMEPLACE_ENABLED=true` on both hosts, `SAMEPLACE_REALTIME_ENABLED=true`, `SAMEPLACE_REALTIME_SINGLE_WORKER=true`, `WEB_CONCURRENCY=1`, `SAMEPLACE_REALTIME_ORIGINS=http://localhost:3000` on the local backend (exact browser origin, not a wildcard). Backend and browser Firebase must use the approved local demo project and matching emulators. Existing `BACKEND_ORIGIN` points to the local backend; `PORTFOLIO_LAB_ORIGIN` is the matching origin if configured. Render must use HTTPS/WSS and the exact configured origin when later approved. Do not use keepalive cron. The single-worker acknowledgement and configured `WEB_CONCURRENCY=1` are necessary but do not prove actual instance/worker count; Owner must verify one instance, one worker, no horizontally scaled deployment before enabling. Process-local capacity is not distributed enforcement. Different origins, query strings, invalid/expired/replayed tickets, unknown frames and failed reauth fail closed. Do not log tickets, authorization or frame bodies.

## Protocol v1

Transport: `GET` upgrade at `/api/sameplace/realtime`, then first frame `{ "type": "auth", "ticket": "<opaque>" }` within 5 seconds. No credential in URL, query, browser storage or snapshot. Ticket expires after 25 seconds, one use, bound to UID, slug, exact Origin. Maximum 32 pending handshakes, 128 tickets (4 per UID), 120 active socket connections, 2 tabs per UID. Application frame bound 1,024 characters; hosting-level WS frame size and connection-pressure controls still need release verification. Only client `ping` after auth; mutation commands remain typed HTTP with authoritative identity and permissions. `pong` does not read or write Firestore. WebSocket send deadline 5 seconds; no growing event queue. One coalesced snapshot per changed revision, checked at most once per second in process memory. The polling of memory is not a Firestore listener or HTTP polling. Reauth every 60 seconds; lease expires after 90 seconds. Stale members and expired proposals are removed lazily and while active sockets run. Empty meeting grace is 90 seconds, no database traffic or background scheduling in empty rooms. A restart forgets ephemeral meetings, proposals and last-seen state; durable rooms, profiles, chat and inbox remain.

`room.snapshot` contains `protocol_version=1`, `room_id`, `meeting_id`, `sequence`, `room_revision`, `chat_revision`, `inbox_revision`, `server_now_ms`, `people`, `proposals`. Each person has opaque public ID, nickname, preset avatar, location, visit/watch presentation, `self`. No raw UID, credential, provider/contact info, friend presence or other-room metadata. `room_revision` is an invalidation hint, not authoritative room document version. `chat_revision` prompts authorized chat GET only on changes and bootstrap. `inbox_revision` is scoped per user, prompts an open social panel to fetch; unopened panels fetch on demand. The frontend validates protocol, expected room ID and sequence, discards old frames and clears active projections on disconnect/revocation. Room metadata is refetched on changed revisions/recovery. Error frames contain stable machine code only; close code 4403 denied/revoked, 4409 waiting/conflict, 1013 unavailable, 4400 invalid. Authentication/projection is not a cache of room membership forever.

Core room changes call the project-owned post-commit observer. Archive or member removal/block fences concurrent admission and removes matching leases/tickets before the command returns. Other core changes fence admission and mark room revisions; new limits do not evict existing participants. Existing socket sees revocation on the next memory check (nominally <=1 s, subject to network/scheduling). A direct provider-side change or crash between commit and publication is recovered by reauth/next authoritative read, not claimed instantaneous. Identity verification is never bypassed by a previous ticket. There is a small commit-to-invalidation window; no cross-worker safety claim. Future activity commands must also use durable seat/active-session locks and private viewer projections.

## Admission and graceful fallback

First admitted user opens the meeting, even if Owner is absent. Duplicate tabs share one participant slot, with independent leases. One UID may occupy one meeting at a time; close the other room to move, or wait for lease expiry. Effective limit is min(room.capacity, policy.capacity_ceiling), with global active room/participant limits. Existing admitted users are not evicted by a lower global policy; new admissions are blocked. Wait is retry-based first successful admission, not a durable FIFO queue or promised place. Browser backs off 15/30/60/120 s with jitter, >=60 s in hidden tabs and honors HTTP `Retry-After` up to 600 s. Disabled realtime stops automatic retry. No continuous HTTP presence heartbeat or view polling. Disconnected view explicitly shows degraded state, hides roster/location proposals and live chat, supports manual read-only history and existing room refresh through authenticated HTTP. On 401/403/404 authorization failure active state is cleared; no unsupported claim that an already delivered historical message can be remotely erased. Future strict distributed revocation would require a different coordination layer.

## Location and layout

Current meeting locations are `lounge` and `table` placeholders. Organizer/room owner proposes a location and visit/watch/play intent to actual participants; recipients answer, decline, cancel (issuer only), or expire in two minutes. Accept moves the participant to the placeholder, never creates a seat, game, result or ranking. Decline stays in place. Proposals and bounded request receipts are meeting-local and vanish on restart. Room shell persists as a dedicated component; the own participant is placed in the 2/3/4 or perimeter arrangement and observers separately; full visual/mobile acceptance remains required. SP05 will attach activity lifecycle and safe pause/move invariants rather than letting this placeholder bypass an active game. No active game exists in SP03.

## Future audio/video, music and activity

One logical connection per active tab is the intended transport for future private activity projections, media signaling and music state. No separate socket per module. SP04 adds interior/music state; SP05 adds activity contract/authorization; SP07 adds audio/video and verified free capacity. Do not stream video through FastAPI or enable TURN/SFU billing. No recording, microphone permission, automatic provider enrollment or media UI claims in SP03. Any transport/provider adapter must maintain origin/auth, capacity, rate limits and no raw secret-state broadcasts.
