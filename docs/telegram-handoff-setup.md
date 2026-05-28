# Telegram Handoff Setup

## Purpose

This document explains how to configure the current Telegram handoff notification flow.

The current implementation is a notification-only handoff:

```text
Visitor uses /chat
-> visitor explicitly chooses "Connect me with Alex"
-> frontend sends the current transcript to POST /api/escalations
-> backend sends a Telegram notification to the configured owner chat
-> visitor can continue with the AI assistant while waiting
```

This is not yet a live two-way bridge. Replies from Telegram back to the website are a later stage.

---

## Current Scope

Implemented:

- explicit user consent before transcript sharing;
- transcript validation and size limits;
- honeypot field;
- escalation rate limiting;
- backend-only Telegram token;
- safe browser errors;
- Telegram message splitting for long notifications.

Not implemented yet:

- Telegram webhook;
- replies from Telegram back to the website;
- Redis TTL session store;
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

For the current notification-only stage, the backend needs the destination chat id:

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

## Render Backend Environment Variables

Set these on the backend service, not on the frontend:

```text
TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_OWNER_CHAT_ID=<owner Telegram chat id>
ESCALATION_DAILY_LIMIT_PER_IP=3
ESCALATION_TRANSCRIPT_MAX_MESSAGES=20
ESCALATION_TRANSCRIPT_MAX_CHARS=8000
```

Notes:

- `TELEGRAM_BOT_TOKEN` must remain backend-only.
- `TELEGRAM_OWNER_CHAT_ID` identifies where handoff notifications are sent.
- `ESCALATION_DAILY_LIMIT_PER_IP` limits abuse of the handoff endpoint.
- Transcript limits should stay aligned with backend validation.

After changing Render environment variables, redeploy the backend service.

---

## Local Development

Local `.env` location:

```text
backend/.env
```

Use:

```text
TELEGRAM_BOT_TOKEN=""
TELEGRAM_OWNER_CHAT_ID=""
```

When both Telegram values are empty in `local` or `test`, the backend uses a no-op notifier for development and tests.

If one Telegram value is set without the other, production-style configuration is incomplete and escalation should fail safely.

---

## Smoke Test

### 1. Check backend readiness

```powershell
Invoke-RestMethod "https://alextym.com/api/health/ready"
```

This currently verifies the general app, Qdrant, LLM, and contact email readiness. It does not yet expose Telegram handoff readiness.

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

Expected response:

```json
{
  "status": "ok"
}
```

Expected result:

```text
A new handoff notification appears in the configured Telegram chat.
```

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
- Telegram API request failed or timed out.

### No Telegram message, but API returns `ok`

Check whether the request filled the honeypot field:

```text
company_website
```

If the honeypot is filled, the backend returns generic success and intentionally does not send a notification.

---

## Security Rules

- Never expose `TELEGRAM_BOT_TOKEN` to frontend code.
- Never use `NEXT_PUBLIC_*` for Telegram secrets.
- Send transcript only after explicit visitor consent.
- Do not log full transcripts in production logs.
- Keep browser-facing errors generic.
- Keep rate limiting enabled.
- Do not use Tool Calling to trigger Telegram side effects directly.

---

## Next Planned Stage

The next larger stage is the live handoff bridge:

```text
website chat <-> backend session <-> Telegram bot <-> Alex
```

Target design:

- Redis TTL session store;
- Telegram webhook;
- webhook secret token validation;
- Server-Sent Events for Alex replies back to the browser;
- no PostgreSQL in the MVP;
- no local SQLite for production state on free hosting.

That stage should be implemented separately from this setup documentation.
