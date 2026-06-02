# Telegram Handoff Setup

## Purpose

This document explains how to configure the Telegram live handoff flow.

The current implementation supports:

```text
Visitor uses /chat
  -> visitor explicitly chooses "Connect me with Alex" / owner handoff
  -> frontend sends the current transcript to POST /api/escalations
  -> backend validates consent, availability, honeypot, rate limit, and transcript size
  -> backend stores a temporary handoff session in Upstash Redis TTL when configured
  -> backend sends a Telegram control message and transcript to the configured owner chat
  -> frontend opens an SSE stream at GET /api/escalations/{handoff_id}/stream
  -> owner replies to the Telegram handoff message
  -> Telegram sends the reply to POST /api/telegram/webhook
  -> backend validates the webhook secret and owner chat id
  -> backend stores the owner reply in the temporary Redis handoff session
  -> browser receives the owner reply through SSE
  -> visitor messages during handoff go to POST /api/escalations/{handoff_id}/messages
  -> backend forwards visitor messages to Telegram
  -> visitor can close handoff through POST /api/escalations/{handoff_id}/close
```

No PostgreSQL is required for the current live handoff implementation. Redis is used for temporary active handoff sessions and, when configured, rate limiting.

---

## Current scope

Implemented:

- explicit user consent before transcript sharing;
- transcript validation and fixed backend schema size limits;
- honeypot field;
- handoff availability window;
- escalation request rate limiting;
- escalation message rate limiting;
- Redis-backed rate limiting through Upstash Redis REST when configured;
- in-memory rate-limiter fallback;
- backend-only Telegram token;
- backend-only Upstash Redis token;
- safe browser errors;
- Telegram control message with `Handoff ID`;
- Telegram transcript delivery as text document when a handoff id exists;
- optional Redis TTL session storage through Upstash Redis REST API;
- handoff id returned from `POST /api/escalations` when Redis storage is configured;
- Telegram webhook endpoint at `POST /api/telegram/webhook`;
- Telegram webhook secret-token validation;
- owner-chat validation;
- owner replies stored in the temporary handoff session;
- Server-Sent Events at `GET /api/escalations/{handoff_id}/stream`;
- browser-side handoff mode;
- visitor follow-up messages sent to Telegram through `POST /api/escalations/{handoff_id}/messages`;
- explicit handoff close endpoint: `POST /api/escalations/{handoff_id}/close`;
- frontend “End handoff” button.

Not implemented:

- richer Telegram operator commands such as `/status` or `/help`;
- Telegram `/close hnd_...` command;
- tool-calling / model-triggered Telegram side effects;
- long-term chat history storage;
- frontend E2E coverage for the full handoff/SSE flow.

---

## Required Telegram setup

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

Treat this value as backend configuration.

---

## Redis TTL session store

### Why Redis TTL is used

The live handoff bridge needs temporary state so Telegram replies can be mapped back to a website chat.

This is not long-term chat history storage. It is temporary active-session state only.

Stored temporarily:

```text
handoff_id
state
created_at
expires_at
transcript
messages
```

Default TTL:

```text
ESCALATION_SESSION_TTL_SECONDS=7200
```

That is 2 hours.

### Upstash Redis REST

The current implementation uses Upstash Redis REST API, not a TCP Redis client.

Reason:

- no extra Python Redis dependency is required;
- HTTP REST calls work on Render Free;
- tokens remain backend-only;
- the same Upstash configuration can support temporary handoff sessions and daily rate limiting.

Required variables:

```text
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
ESCALATION_SESSION_TTL_SECONDS
```

Current behaviour:

```text
If both Upstash values are empty:
  - handoff notification can still be sent if Telegram is configured;
  - no handoff_id is returned;
  - live browser stream and owner replies cannot work.

If only one Upstash value is configured:
  - handoff session storage is treated as misconfigured;
  - related flows fail safely instead of silently losing messages.

If both values are configured:
  - POST /api/escalations stores the temporary handoff session;
  - response includes handoff_id;
  - SSE stream and Telegram replies can work.
```

---

## Telegram webhook

### Why webhook is needed

The webhook lets the backend receive messages sent by the owner to the bot.

Intended Telegram workflow:

```text
1. A visitor starts handoff on /chat.
2. The backend sends a Telegram control message with a Handoff ID.
3. The owner replies directly to a Telegram handoff message containing that Handoff ID.
4. Telegram sends the reply update to POST /api/telegram/webhook.
5. The backend verifies the webhook secret and owner chat id.
6. The backend extracts the Handoff ID.
7. The backend stores the owner reply in the Redis TTL handoff session.
8. The browser receives the reply from GET /api/escalations/{handoff_id}/stream.
```

### Required variables

```text
TELEGRAM_WEBHOOK_SECRET
TELEGRAM_WEBHOOK_URL
```

`TELEGRAM_WEBHOOK_SECRET` must be the same secret token used when registering the Telegram webhook.

`TELEGRAM_WEBHOOK_URL` is a documentation/configuration value for the public webhook URL, for example:

```text
https://alextym.com/api/telegram/webhook
```

The backend validates the request header against `TELEGRAM_WEBHOOK_SECRET`; it does not need `TELEGRAM_WEBHOOK_URL` at request time.

### Register webhook

Example PowerShell shape:

```powershell
$body = @{
  url = "https://alextym.com/api/telegram/webhook"
  secret_token = "<TELEGRAM_WEBHOOK_SECRET>"
  allowed_updates = @("message")
  drop_pending_updates = $true
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### Verify webhook

```powershell
Invoke-RestMethod "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

Expected:

```text
url: https://alextym.com/api/telegram/webhook
pending_update_count: low/0 after processing
last_error_message: empty
```

---

## Backend environment variables

Set these on the backend service, not on the frontend:

```text
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_OWNER_CHAT_ID=<owner Telegram chat id>
TELEGRAM_WEBHOOK_SECRET=<random secret token used in setWebhook>
TELEGRAM_WEBHOOK_URL=https://alextym.com/api/telegram/webhook

UPSTASH_REDIS_REST_URL=<Upstash REST URL>
UPSTASH_REDIS_REST_TOKEN=<Upstash REST token>
ESCALATION_SESSION_TTL_SECONDS=7200

HANDOFF_AVAILABILITY_ENABLED=true
HANDOFF_AVAILABILITY_TIMEZONE=Europe/London
HANDOFF_AVAILABILITY_START=09:00
HANDOFF_AVAILABILITY_END=21:00

ESCALATION_DAILY_LIMIT_PER_IP=10
ESCALATION_MESSAGE_DAILY_LIMIT_PER_IP=50
```

Notes:

- `TELEGRAM_BOT_TOKEN` must remain backend-only.
- `TELEGRAM_OWNER_CHAT_ID` identifies where handoff notifications are sent.
- `TELEGRAM_WEBHOOK_SECRET` protects the webhook endpoint.
- `UPSTASH_REDIS_REST_TOKEN` must remain backend-only.
- `ESCALATION_DAILY_LIMIT_PER_IP` limits abuse of the handoff creation endpoint.
- `ESCALATION_MESSAGE_DAILY_LIMIT_PER_IP` limits visitor messages sent to Telegram during active handoff.
- `ESCALATION_SESSION_TTL_SECONDS` controls how long the temporary handoff record exists.
- Handoff availability variables control whether live handoff is offered in the current time window.
- Transcript and message size limits are backend schema constants.

Do not configure these obsolete variables:

```text
ESCALATION_TRANSCRIPT_MAX_MESSAGES
ESCALATION_TRANSCRIPT_MAX_CHARS
```

After changing backend environment variables, redeploy the backend service.

---

## Local development

Local `.env` location:

```text
backend/.env
```

For notification-only local development:

```text
TELEGRAM_BOT_TOKEN=""
TELEGRAM_OWNER_CHAT_ID=""
TELEGRAM_WEBHOOK_SECRET=""
TELEGRAM_WEBHOOK_URL=""
UPSTASH_REDIS_REST_URL=""
UPSTASH_REDIS_REST_TOKEN=""
```

When both Telegram notification values are empty in `local` or `test`, the backend uses a no-op notifier for development and tests.

When both Upstash values are empty, the backend skips temporary session persistence and live stream storage.

Webhook local development requires a public HTTPS tunnel such as ngrok or Cloudflare Tunnel:

```text
https://<tunnel-host>/api/telegram/webhook
```

Register that tunnel URL with `setWebhook` during local webhook testing.

---

## Smoke test

### 1. Check backend readiness

```powershell
Invoke-RestMethod "https://alextym.com/api/health/ready"
```

This verifies configuration presence for Qdrant, LLM, and contact email. It does not perform live provider network checks and does not expose Redis handoff readiness.

### 2. Test escalation endpoint

```powershell
$body = @{
  consent_accepted = $true
  reason = "user_requested_human"
  transcript = @(
    @{
      role = "user"
      content = "Can I speak to the owner?"
    },
    @{
      role = "assistant"
      content = "Would you like me to connect you with the owner?"
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

The Telegram notification should include the handoff id.

### 3. Test Telegram reply capture and browser delivery

1. Open `/chat` in a browser.
2. Start a handoff through the UI.
3. Reply directly to the Telegram handoff notification.
4. Keep the browser tab open.

Expected behaviour:

```text
Telegram -> POST /api/telegram/webhook -> backend validates secret
  -> backend stores owner reply in Redis TTL session
  -> browser receives the reply through GET /api/escalations/{handoff_id}/stream
```

### 4. Test visitor message forwarding to Telegram

After handoff is active, send another message from the website chat.

Expected behaviour:

```text
browser -> POST /api/escalations/{handoff_id}/messages
  -> backend validates the active session
  -> backend forwards the visitor message to Telegram
```

Expected Telegram result:

```text
A new visitor message from alextym.com
Handoff ID: hnd_...
User: ...
```

Reply to that Telegram message to send an answer back to the website chat.

### 5. Test handoff close

Click the frontend handoff close button.

Expected behaviour:

```text
browser -> POST /api/escalations/{handoff_id}/close
  -> backend marks session as closed
  -> SSE stream emits closed or the UI switches to closed state
  -> new visitor messages use the normal AI chat path
```

---

## Troubleshooting

### 403: Handoff unavailable

Likely causes:

- current time is outside the configured availability window;
- `HANDOFF_AVAILABILITY_ENABLED=true`;
- timezone/start/end values are not what you expect.

### 403: Invalid Telegram webhook secret

Likely causes:

- `secret_token` used in `setWebhook` does not match `TELEGRAM_WEBHOOK_SECRET`;
- `TELEGRAM_WEBHOOK_SECRET` contains extra spaces or quotes;
- webhook was registered before the latest secret value was deployed.

### 404: Escalation session was not found

Likely causes:

- the handoff session expired;
- Redis TTL removed the session;
- the visitor used an old page after deployment;
- the wrong `handoff_id` was used;
- session storage was not configured when the handoff was created.

### 502: Telegram reply could not be processed

Likely causes:

- Upstash Redis REST request failed;
- Upstash Redis token is invalid;
- the handoff session payload in Redis is corrupted.

### 502: Could not send this message to Alex / owner

Likely causes:

- Telegram Bot API request failed;
- Telegram token is invalid;
- owner chat id is wrong;
- the bot was blocked;
- the owner never started the bot.

### Webhook returns `ignored`

Expected for:

- messages not sent from `TELEGRAM_OWNER_CHAT_ID`;
- messages without text;
- messages not replying to a handoff notification;
- replies to expired handoff sessions;
- replies to Telegram messages that do not contain a `Handoff ID`.

---

## Security rules

- Never expose `TELEGRAM_BOT_TOKEN` to frontend code.
- Never expose `UPSTASH_REDIS_REST_TOKEN` to frontend code.
- Never use `NEXT_PUBLIC_*` for Telegram or Redis secrets.
- Send transcript only after explicit visitor consent.
- Do not log full transcripts in production logs.
- Keep browser-facing errors generic.
- Keep rate limiting enabled.
- Use TTL for temporary handoff sessions.
- Validate `X-Telegram-Bot-Api-Secret-Token` for every webhook request.
- Accept webhook replies only from `TELEGRAM_OWNER_CHAT_ID`.
- Do not use tool-calling to trigger Telegram side effects directly.

---

## Known technical debt

- Add richer Telegram operator commands:
  - `/status`;
  - `/help`;
  - `/close hnd_...`.
- Improve Telegram reply routing if multiple handoffs are active.
- Add frontend E2E tests for handoff UI and SSE delivery.
- Consider stronger transcript retention and deletion policy if the project grows.
- Consider a persistent audit/logging strategy only if there is a real operational need.
