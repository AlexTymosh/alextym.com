# Redis escalation sessions: atomic updates

## Why

The former Upstash adapter read a complete session with `GET`, computed a pure
Python state transition, and wrote JSON via `SET EX`. Concurrent requests
could overwrite one another or reopen an already closed handoff.

## Approach

- Keep `EscalationSessionRecord` and state-transition rules in `app.domain`.
- Read the exact raw JSON snapshot with `GET`.
- Derive the next state and remaining TTL using the existing Python domain code.
- Execute one Upstash REST `EVAL` command. Lua compares the current JSON bytes
  against the snapshot and performs `SET EX` or `DEL` only on a match.
- On mismatch, reread and recompute; after eight conflicts, fail closed rather
  than overwrite somebody else's update.

The Lua script contains **no domain business rules**. The CAS check and write
run as one atomic server operation, so an append cannot resurrect a closed
session. Concurrent message appends preserve both messages as long as conflict
retries succeed.

## Invariants

- Redis key, JSON fields, state strings, message roles and ID formats unchanged.
- Existing `expires_at` is not extended; each successful update writes `EX`
  using the remaining lifetime computed by the domain transition.
- Already closed sessions keep the existing idempotent close behaviour.
- Redis keys missing at update time cannot be resurrected by CAS.
- An unexpected EVAL reply or excessive conflicts raises
  `EscalationSessionStoreError`; HTTP error translation is unchanged.
- Session `close` still retains transcript JSON until its TTL expires; purge
  and retention policy belong to Step 10C.
- No new environment variables, Redis keys, Docker infrastructure or secrets.

## Testing limits

Local tests deterministically simulate Redis command semantics and force
concurrent reads. They do **not** execute Lua on a production Upstash instance.
Run normal `task ci` and GitHub CI before merge; perform an explicit approved
Upstash integration smoke on a non-production database before relying on the
new atomic guarantees operationally.

Source: Upstash Redis REST API documentation on `EVAL` and scripting.
