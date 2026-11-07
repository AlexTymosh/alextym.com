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

## Step 10C — explicit server purge on Reset

- `POST /api/escalations/{handoff_id}/close` remains unchanged. It preserves
  session state and messages until the original expiry so SSE readers can
  receive pending messages followed by `session_closed`.
- `DELETE /api/escalations/{handoff_id}` is a separate, idempotent operation:
  the server returns `204 No Content` only after Redis confirms a `DEL`
  result of `0` (already missing) or `1` (removed). Storage failure returns
  a safe `502`, missing configuration returns `503`.
- `Reset chat` purges any known handoff, including one manually closed before
  Reset. Late-created, detached handoffs are also purged.
- Redis session `expires_at` and TTL remain unchanged for all sessions not
  explicitly purged. No new persistent keys, tokens, or personal-data copies.
- A handoff ID is an unguessable capability for existing session endpoints;
  the DELETE endpoint uses that same capability model. Review authorization
  requirements separately if these IDs become exposed or guessable.
- This is NOT proof of end-to-end erasure. Telegram messages already sent,
  operator devices, upstream logs, backups, in-flight notifications and other
  downstream copies are not deleted. The client cannot report confirmed
  deletion if it loses the response. Manual `close` does not purge data.
- There is deliberately no configurable purge-on-close retention period in
  this PR. Automatic Redis expiry remains governed by the existing TTL.
- Deploy the backend DELETE route before (or together with) the frontend;
  during a version mismatch, reset cleanup can return 404 and fail best effort.

Validation: backend API/storage acknowledgement tests and frontend
Playwright reset and helper tests. Run full `task ci` and GitHub CI before merge.
