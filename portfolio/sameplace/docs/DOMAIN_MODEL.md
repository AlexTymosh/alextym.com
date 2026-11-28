# Room core domain model — SP02

Normative requirements: SP-TRS-001 sections 4–7. Room is a durable aggregate; meeting, presence, game seat and activity are separate future lifecycles. SP02 has no online occupancy or game state. The `rooms` endpoint lists room metadata a user is permitted to access, not who is online.

## Durable records, schema version 1

One server-only Firestore collection `sameplace_room_core_v1`, with explicitly prefixed document keys:

| Key | Fields and invariants |
|---|---|
| `policy` | Storage cap, stored-room counter, active-room and active-human limits (reserved for SP03), configured capacity ceiling. Only verified platform Owner can change it. Storage cap includes archived rooms. Defaults: 100 saved rooms, four simultaneous rooms, 20 simultaneous humans, capacity ceiling 10. The latter three are configured values, not verified media capacity. |
| `user_<sha256(uid)>` | UID, creator approval, active owned room IDs (max 3), accessible room IDs (max 100). Membership and indexes are updated atomically; no scan across other users. |
| `slug_<slug>` | Immutable mapping to room ID. Reservation survives archive and rename. |
| `room_<uuid>` | UUID, slug, display name, owner UID, version, status, configured capacity, private visibility, interior preset ID, lounge location, membership map, bounded invitation records, optional transfer. Single authoritative owner, membership independent of online presence. |
| `command_<sha256(uid + NUL + request_id)>` | Request fingerprint, safe subject reference, timestamp. No raw token or projection. |
| `audit_<uuid>` | Actor UID, stable action, safe subject, timestamp. No invitation token, email, credentials or game state. |

Active member entries have a status and explicit role list; ownership is a separate room field. Removed/blocked records remain as tombstones to invalidate old links. Revocation version is used instead of a client clock. A maximum of 100 member/tombstone entries and 50 nonexpired invite records per room bounds the aggregate; capacity (2–10) is an independent limit on future simultaneous humans, not the number of members. Expired invite metadata is pruned on the next invitation creation. No background jobs. Command/audit records are retained in SP02; bounded retention/export/cleanup must be designed and verified against the free delete quota before production; no paid TTL enabled.

## Transaction boundaries

Every operation uses `Store.run(callback)`. The Firestore adapter buffers writes until the operation completes, so every SDK read precedes every SDK write. It uses the injected host client and transaction decorator, three attempts. MemoryStore is a serializable test double only. No production fallback to memory. ID generation/time and invitation secret are captured before SDK retries. Create reserves slug, room, owner count, membership, policy count, command receipt and audit in one transaction. Transfer updates both owner counters and ownership in one transaction; it requires an approved target member, a proposal, target confirmation, a matching version and an unexpired proposal (24h). Previous owner becomes ordinary member. Archive removes active ownership slot, invalidates pending invites and transfer, but keeps room/members/slug. Restore requires approval, slot and current capacity ceiling. No delete or overwrite of existing room ID. The platform Owner may create rooms intrinsically; to receive another user's ownership they should have explicit creator approval on their own UID, like any target of a proposal.

A request ID is stable for a retry. Identical accepted mutation retries return current authorized projection, not another write; conflicting payload/action/subject returns 409. Invite creation returns the raw token only on first successful response; retries never mint another or replay the plaintext. If the client lost the response, revoke the pending invitation and explicitly issue another. Redeem retry with the same request ID returns current member projection only while access remains valid; another request ID cannot consume the same invitation again. Room edit and moderation commands compare `version`. The UI does not auto-retry mutations; after a network failure refresh state first.

## Deferred lifecycle

Meeting admission, lease, distinct online UID counting, global active limits, waiting state, favourites and recent visits: SP03. Interiors have only stable preset identifiers; art/editor/audio SP04. Activities and archived unfinished sessions SP05. This is not yet the product release; all new routes remain disabled by default.


## SP03 additive state (schema v1)

Existing `sameplace_room_core_v1` document namespace and `Store.run(UnitOfWork)` port are reused. No migration, eager initialization or Firestore rule change. All reads precede staged writes in the adapter. Existing room/member/slug/approval records are unchanged.

| Key | Fields and invariants |
|---|---|
| `social_<sha256(uid)>` | Internal UID; derived opaque public ID (128-bit hash domain-separated from other IDs), nickname, preset avatar, privacy, bilateral relationship map, favourite/recent room IDs, bounded inbox and sender ping window. Public projection excludes UID, email, contacts and private settings of others. |
| `public_<public_id>` | Server-only mapping to UID, created lazily on profile save, visit or authorized social mutation. No directory or email search. Reject conflicting mapping. |
| `chat_<room_id>` | Bounded room aggregate, ordered server timestamps and opaque message IDs; plain text, author public ID/nickname snapshot, expiry, hidden flag/reason. Hide removes text; reads filter hidden/expired independently of physical cleanup. |
| Existing `command_`, `audit_` | Reuse SP02 idempotent fingerprint and audit metadata for durable social mutations. No plaintext message or contact payload in audit. |

Friend transitions: request creates symmetric outgoing/incoming; only recipient accepts/declines; requester cancels; accepted pair can be removed; independent blocks prevent social lookup/pings but never change room grants. Terminal declined/cancelled relationships are removed from the bounded map; receipt/audit remains. Profiles can persist after room revocation (friendship independent), but room lists/notices are filtered by current memberships. Profile scope requires owner, approval, indexed membership or existing profile. Room access uses authoritative SP02 membership; archived rooms cannot admit or serve active chat. Chat retention 30 days; current members read available history; per-room 500 messages/400 kB hard cap; expired records are pruned on send or moderator cleanup. Notices expire after seven days, independent of chat; no contact fields. All durable times are server UTC ms.

Ephemeral: `Meeting` has room ID, opaque meeting ID, sequence, room/chat revisions, idle grace, participants and proposals. `Person` owns public projection, location, visit/watch role, at most two connection leases and bounded command receipts. One UID admitted once per meeting and only one active meeting globally. `Ticket` contains memory-only verified credential and exact origin, 25 s expiry, single use. Active counts, ticket/connection IDs, proposal state and approximate opted-in last seen are not persisted. Restart clears them; no durable room/game changes. Location intent does not equal game seat; SP05 integrates activity lifecycle and durable game seat locks. Presence outside active room is not tracked by this stage.

## SP04 stored records

Within `sameplace_room_core_v1`, `decor_<room-id>` stores schema_version 1, optional published scenes keyed by lounge/table, music states keyed by room/lounge/table and monotonic `music_versions` including inheritance tombstones. Scene revision 0 is a computed default, never persisted as a published scene. Source ID, playback status, position_ms, started_at_ms and changed_by public ID are independent of scene data. `scene_library_<hash(uid)>` stores schema_version 1 and up to 12 template records (id, revision, name, scene, updated_at_ms); each scene is copied on publication. Room archival preserves these documents. No eager migration; reads do not create records. Max 16 objects/scene. Existing durable receipts and audits cover writes. No game state stored by this module.

## SP05 ephemeral media domain

`MediaState` owns a meeting-keyed Session: room/local mode, one Endpoint per UID (active connection, public ID, opt-in track flags, bounded inbox and signal rate), temporary moderator mute set and pair-generation identifiers. The existing Hub owns authoritative presence/location; MediaState observes it under the same lock, never creates a game seat or alters durable room state. Pair removed when endpoint/channel no longer permitted; obsolete signaling pruned. Local preference model is versioned browser-only, no credential or device info server-side. Restart loses media policy and endpoints; room/chat remain. No schema migration.
