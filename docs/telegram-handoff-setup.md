# Telegram Handoff Setup

## Purpose

This document explains how to configure the Telegram handoff flow.

The current implementation supports:

```text
Visitor uses /chat
-> visitor explicitly chooses "Connect me with Alex"
-> frontend sends the current transcript to POST /api/escalations
-> backend optionally stores a temporary handoff session in Redis TTL storage
-> backend sends a Telegram notification to the configured owner chat
-> visitor can continue with the AI assistant while waiting
```

Replies from Telegram back to the website are a later stage. This stage only introduces the temporary Redis TTL session store needed for the future live bridge.

---

## Current Scope

Implemented:

- explicit user consent before transcript sharing;
- transcript validation and size limits;
- honeypot field;
- escalation rate limiting;
- backend-only Telegram token;
- safe browser errors;
- Telegram message splitting for long notifications;
- optional Redis TTL session storage through Upstash Redis REST API;
- handoff id returned from `POST /api/escalations` when Redis storage is configured;
- handoff id included in the Telegram notification when Redis storage is configured.

Not implemented yet:

- Telegram webhook;
- replies from Telegram back to the website;
- Server-Sent Events for live handoff messages;
- Tool Calling / structured model-triggered handoff proposals.

---

## Required Telegram Setup

### 1. Create a Telegram bot

Use Telegram's official bot management account:

```text
@BotFather
```

Create a new bot and copy the bot token.

The token must be stored only in backend environment variables.

Required variable:

```text
TELEGRAM_BOT_TOKEN
```

Never commit the token to GitHub.

---

### 2. Start a chat with the bot

Open the bot in Telegram and send:

```text
/start
```

The bot cannot send messages to a private Telegram chat until the owner starts the conversation.

---

### 3. Get the owner chat id

The backend needs the destination chat id:

```text
TELEGRAM_OWNER_CHAT_ID
```

One manual way to get it:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

After sending `/start` to the bot, inspect the response and find:

```json
{
  "message": {
    "chat": {
      "id": 123456789
    }
  }
}
```

Use that `id` value as `TELEGRAM_OWNER_CHAT_ID`.

Do not commit it if you prefer to treat it as private configuration.

---

## Redis TTL Session Store

### Why Redis TTL is used

The live handoff bridge needs temporary state so future Telegram replies can be mapped back to a website chat.

This is not long-term chat history storage. It is temporary active-session state only.

Stored temporarily:

```text
handoff_id
state
created_at
expires_at
transcript
```

Default TTL:

```text
ESCALATION_SESSION_TTL_SECONDS=7200
```

That is 2 hours.

### Upstash Redis REST

The current implementation uses Upstash Redis REST API, not a TCP Redis client.

Reason:

- no new Python runtime dependency is required;
- no `uv.lock` change is needed;
- HTTP REST calls work well on Render Free;
- the token remains backend-only.

Required variables:

```text
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
ESCALATION_SESSION_TTL_SECONDS
```

If both Upstash values are empty, escalation continues to work as notification-only and no handoff id is returned.

If only one Upstash value is configured, escalation fails safely instead of silently running with broken session storage.

If both values are configured, `POST /api/escalations` stores the temporary handoff session and returns a `handoff_id`.

---

## Render Backend Environment Variables

Set these on the backend service, not on the frontend:

```text
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_OWNER_CHAT_ID=<owner Telegram chat id>
ESCALATION_DAILY_LIMIT_PER_IP=3
ESCALATION_TRANSCRIPT_MAX_MESSAGES=20
ESCALATION_TRANSCRIPT_MAX_CHARS=8000
UPSTASH_REDIS_REST_URL=<Upstash REST URL>
UPSTASH_REDIS_REST_TOKEN=<Upstash REST token>
ESCALATION_SESSION_TTL_SECONDS=7200
```

Notes:

- `TELEGRAM_BOT_TOKEN` must remain backend-only.
- `TELEGRAM_OWNER_CHAT_ID` identifies where handoff notifications are sent.
- `UPSTASH_REDIS_REST_TOKEN` must remain backend-only.
- `ESCALATION_DAILY_LIMIT_PER_IP` limits abuse of the handoff endpoint.
- Transcript limits should stay aligned with backend validation.
- Session TTL controls how long the temporary handoff record exists.

After changing Render environment variables, redeploy the backend service.

---

## Local Development

Local `.env` location:

```text
backend/.env
```

For notification-only local development:

```text
TELEGRAM_BOT_TOKEN=""
TELEGRAM_OWNER_CHAT_ID=""
UPSTASH_REDIS_REST_URL=""
UPSTASH_REDIS_REST_TOKEN=""
```

When both Telegram values are empty in `local` or `test`, the backend uses a no-op notifier for development and tests.

When both Upstash values are empty, the backend skips temporary session persistence and keeps notification-only behaviour.

---

## Smoke Test

### 1. Check backend readiness

```powershell
Invoke-RestMethod "https://alextym.com/api/health/ready"
```

This verifies the general app, Qdrant, LLM, and contact email readiness. It does not expose Redis handoff readiness yet.

### 2. Test escalation endpoint

```powershell
$body = @{
  consent_accepted = $true
  reason = "user_requested_human"
  transcript = @(
    @{
      role = "user"
      content = "Can I speak to Alex?"
    },
    @{
      role = "assistant"
      content = "Would you like me to connect you with Alex?"
    }
  )
  company_website = ""
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri "https://alextym.com/api/escalations" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Expected response without Redis configured:

```json
{
  "status": "ok"
}
```

Expected response with Redis configured:

```json
{
  "status": "ok",
  "handoff_id": "hnd_...",
  "state": "waiting_for_alex",
  "expires_in_seconds": 7200
}
```

Expected Telegram result:

```text
A new handoff notification appears in the configured Telegram chat.
```

When Redis is configured, the Telegram notification should include the handoff id.

---

## Troubleshooting

### 503: Escalation is not configured

Likely causes:

- `TELEGRAM_BOT_TOKEN` is missing;
- `TELEGRAM_OWNER_CHAT_ID` is missing;
- the variables were added to the frontend service instead of the backend service;
- the backend was not redeployed after changing environment variables.

### 502: Could not connect with Alex

Likely causes:

- invalid bot token;
- invalid chat id;
- the owner has not sent `/start` to the bot;
- Telegram API request failed or timed out;
- Upstash Redis REST URL/token is invalid;
- Upstash Redis REST request failed.

### No Telegram message, but API returns `ok`

Check whether the request filled the honeypot field:

```text
company_website
```

If the honeypot is filled, the backend returns generic success and intentionally does not send a notification.

---

## Security Rules

- Never expose `TELEGRAM_BOT_TOKEN` to frontend code.
- Never expose `UPSTASH_REDIS_REST_TOKEN` to frontend code.
- Never use `NEXT_PUBLIC_*` for Telegram or Redis secrets.
- Send transcript only after explicit visitor consent.
- Do not log full transcripts in production logs.
- Keep browser-facing errors generic.
- Keep rate limiting enabled.
- Use TTL for temporary handoff sessions.
- Do not use Tool Calling to trigger Telegram side effects directly.

---

## Next Planned Stage

The next larger stage is the live handoff bridge:

```text
website chat <-> backend Redis TTL session <-> Telegram bot <-> Alex
```

Target design:

- Telegram webhook;
- webhook secret token validation;
- Server-Sent Events for Alex replies back to the browser;
- no PostgreSQL in the MVP;
- no local SQLite for production state on free hosting.

That stage should be implemented separately from this Redis TTL session storage stage.
