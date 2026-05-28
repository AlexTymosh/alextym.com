# Telegram Handoff Setup

## Purpose

This document explains how to configure the Telegram live handoff flow.

The current implementation supports:

```text
Visitor uses /chat
-> visitor explicitly chooses "Connect me with Alex"
-> frontend sends the current transcript to POST /api/escalations
-> backend stores a temporary handoff session in Upstash Redis TTL
-> backend sends a Telegram notification to the configured owner chat
-> frontend opens an SSE stream at GET /api/escalations/{handoff_id}/stream
-> Alex replies to the Telegram handoff message
-> Telegram sends the reply to POST /api/telegram/webhook
-> backend validates the webhook and owner chat id
-> backend stores Alex's reply in the temporary Redis handoff session
-> browser receives Alex's reply through SSE
-> visitor messages during handoff go to POST /api/escalations/{handoff_id}/messages
-> backend forwards those visitor messages to Telegram
```

No PostgreSQL is required for the current live handoff MVP. Redis is used only for temporary active handoff sessions.

---

## Current Scope

Implemented:

- explicit user consent before transcript sharing;
- transcript validation and fixed backend schema size limits;
- honeypot field;
- escalation request rate limiting;
- escalation message rate limiting;
- backend-only Telegram token;
- backend-only Upstash Redis token;
- safe browser errors;
- Telegram message splitting for long notifications;
- optional Redis TTL session storage through Upstash Redis REST API;
- handoff id returned from `POST /api/escalations` when Redis storage is configured;
- handoff id included in Telegram notifications;
- Telegram webhook endpoint at `POST /api/telegram/webhook`;
- Telegram webhook secret-token validation;
- owner-chat validation;
- Alex replies stored in the temporary handoff session when the owner replies to a Telegram handoff message;
- Server-Sent Events at `GET /api/escalations/{handoff_id}/stream`;
- browser-side handoff mode;
- visitor follow-up messages sent to Telegram through `POST /api/escalations/{handoff_id}/messages`.

Not implemented yet:

- explicit close endpoint / `/close` command;
- richer Telegram operator commands such as `/status` or `/help`;
- Redis-backed rate limiter;
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

- no new Python runtime dependency is required;
- no `uv.lock` change is needed;
- HTTP REST calls work on Render Free;
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

## Telegram Webhook

### Why webhook is needed

The webhook lets the backend receive messages sent by Alex to the bot.

The intended Telegram workflow is:

```text
1. A visitor starts handoff on /chat.
2. The backend sends a Telegram notification with a Handoff ID.
3. Alex replies directly to a Telegram handoff message containing that Handoff ID.
4. Telegram sends the reply update to POST /api/telegram/webhook.
5. The backend verifies the webhook secret and owner chat id.
6. The backend extracts the Handoff ID from the replied-to notification.
7. The backend stores Alex's reply in the Redis TTL handoff session.
8. The browser receives the reply from GET /api/escalations/{handoff_id}/stream.
```

### Required variables

```text
TELEGRAM_WEBHOOK_SECRET
TELEGRAM_WEBHOOK_URL
```

`TELEGRAM_WEBHOOK_SECRET` must be a secret token used when registering the Telegram webhook.

`TELEGRAM_WEBHOOK_URL` is documentation/configuration value for the public webhook URL, for example:

```text
https://alextym.com/api/telegram/webhook
```

The backend endpoint validates `TELEGRAM_WEBHOOK_SECRET`; it does not need `TELEGRAM_WEBHOOK_URL` at request time.

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

## Render Backend Environment Variables

Set these on the backend service, not on the frontend:

```text
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_OWNER_CHAT_ID=<owner Telegram chat id>
TELEGRAM_WEBHOOK_SECRET=<random secret token used in setWebhook>
TELEGRAM_WEBHOOK_URL=https://alextym.com/api/telegram/webhook
UPSTASH_REDIS_REST_URL=<Upstash REST URL>
UPSTASH_REDIS_REST_TOKEN=<Upstash REST token>
ESCALATION_SESSION_TTL_SECONDS=7200
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
- Transcript and message size limits are backend schema constants. Do not configure `ESCALATION_TRANSCRIPT_MAX_MESSAGES` or `ESCALATION_TRANSCRIPT_MAX_CHARS`.

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
TELEGRAM_WEBHOOK_SECRET=""
TELEGRAM_WEBHOOK_URL=""
UPSTASH_REDIS_REST_URL=""
UPSTASH_REDIS_REST_TOKEN=""
```

When both Telegram notification values are empty in `local` or `test`, the backend uses a no-op notifier for development and tests.

When both Upstash values are empty, the backend skips temporary session persistence and keeps notification-only behaviour.

Webhook local development requires a public HTTPS tunnel such as ngrok or Cloudflare Tunnel:

```text
https://<tunnel-host>/api/telegram/webhook
```

Register that tunnel URL with `setWebhook` during local webhook testing.

---

## Smoke Test

### 1. Check backend readiness

```powershell
Invoke-RestMethod "https://alextym.com/api/health/ready"
```

This verifies general app, Qdrant, LLM, and contact email readiness. It does not expose Redis handoff readiness.

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
-> backend stores Alex reply in Redis TTL session
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

---

## Troubleshooting

### 503: Escalation is not configured

Likely causes:

- `TELEGRAM_BOT_TOKEN` is missing;
- `TELEGRAM_OWNER_CHAT_ID` is missing;
- variables were added to the frontend service instead of the backend service;
- backend was not redeployed after changing environment variables.

### 503: Escalation streaming is not configured

Likely causes:

- `UPSTASH_REDIS_REST_URL` is missing;
- `UPSTASH_REDIS_REST_TOKEN` is missing;
- Redis values are configured only partially;
- backend was not redeployed after changing environment variables.

### 503: Telegram webhook is not configured

Likely causes:

- `TELEGRAM_WEBHOOK_SECRET` is missing;
- `TELEGRAM_OWNER_CHAT_ID` is missing;
- `UPSTASH_REDIS_REST_URL` is missing;
- `UPSTASH_REDIS_REST_TOKEN` is missing;
- variables were added to the frontend service instead of the backend service;
- backend was not redeployed after changing environment variables.

### 403: Invalid Telegram webhook secret

Likely causes:

- `secret_token` used in `setWebhook` does not match `TELEGRAM_WEBHOOK_SECRET`;
- `TELEGRAM_WEBHOOK_SECRET` in Render contains extra spaces or quotes;
- webhook was registered before the latest secret value was deployed.

### 404: Escalation session was not found

Likely causes:

- the handoff session expired;
- Redis TTL removed the session;
- the visitor used an old page after deployment;
- the wrong `handoff_id` was used.

### 502: Telegram reply could not be processed

Likely causes:

- Upstash Redis REST request failed;
- Upstash Redis token is invalid;
- the handoff session payload in Redis is corrupted.

### 502: Could not send this message to Alex

Likely causes:

- Telegram Bot API request failed;
- Telegram token is invalid;
- owner chat id is wrong;
- the bot was blocked or the owner never started the bot.

### Webhook returns `ignored`

Expected for:

- messages not sent from `TELEGRAM_OWNER_CHAT_ID`;
- messages without text;
- messages not replying to a handoff notification;
- replies to expired handoff sessions;
- replies to Telegram messages that do not contain a `Handoff ID`.

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
- Validate `X-Telegram-Bot-Api-Secret-Token` for every webhook request.
- Accept webhook replies only from `TELEGRAM_OWNER_CHAT_ID`.
- Do not use Tool Calling to trigger Telegram side effects directly.

---

## Known Technical Debt

- Add explicit handoff close flow:
  - `POST /api/escalations/{handoff_id}/close`;
  - frontend `End handoff` button;
  - Telegram `/close hnd_...` command.
- Improve Telegram reply routing with a separate short control message that always contains the `Handoff ID`.
- Consider Redis-backed rate limiting instead of the current in-memory limiter.
- Consider structured handoff suggestion from AI responses instead of text parsing in the frontend.
- Add frontend E2E tests for handoff UI and SSE delivery.
