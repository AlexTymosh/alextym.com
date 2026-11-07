# Handoff reset — server session cleanup

Reset is a UI operation that discards the conversation, but a human handoff
also exists on the server. Closing an `EventSource` only disconnects the
browser's SSE listener; it does **not** close the server session in Redis.

## Step 10A behaviour

- If Reset is used with a known active handoff ID, make a best-effort request
  to the existing `POST /api/escalations/{handoff_id}/close` endpoint.
- If the `POST /api/escalations` request finishes after its local conversation
  was reset/unmounted, close the newly returned session ID rather than attach
  it to a new chat.
- Reset remains immediate and does not wait on the close request. Cleanup
  results must not mutate the new conversation's UI.
- A handoff already marked `closed` is not closed twice on Reset.
- Keep existing backend TTL, Redis key/value schema, Telegram notification,
  session URL, and SSE format unchanged.

## Limitations and next work

This is **best effort**, not a guaranteed server-side cancellation protocol.
A network failure, missing create response, tab crash, or server failure may
leave a session until its configured TTL. The backend can send a Telegram
notification before the browser receives the handoff ID. Never claim that
Reset reliably deletes all shared data. The existing close operation changes
session state to `closed`; it does **not** delete transcript data immediately.

A later PR should design and test authenticated/idempotent cancellation with
confirmation and explicit retention/privacy semantics. Another independent PR
should make the Redis GET→transition→SET path atomic: concurrent owner replies
and close requests can otherwise overwrite each other.

## Validation

`frontend/e2e/handoff-cleanup.spec.ts` covers the close helper without a server.
The amended `frontend/e2e/chat-reset-races.spec.ts` verifies that active and
late-created handoffs trigger a close request on Reset, while the already
present race tests confirm no stale UI changes. Full `task ci` and GitHub CI
are required before merge.
