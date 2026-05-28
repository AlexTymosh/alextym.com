# Chat Handoff Stage 1

## Purpose

Stage 1 adds a notification-only human handoff path for `/chat`.

The visitor stays on the website. After explicit consent, the current chat transcript is sent to Alex through a backend-only Telegram bot integration.

This stage does not implement live replies from Telegram back into the website chat. That is a later stage and should use temporary session storage and SSE or another server-to-browser delivery mechanism.

---

## User Flow

1. The visitor chats with the AI assistant on `/chat`.
2. The UI offers a handoff action when the assistant cannot answer confidently or when the visitor asks to connect with Alex.
3. The visitor sees consent copy explaining that the current chat history will be shared with Alex.
4. The visitor clicks `Connect me with Alex`.
5. The frontend sends the transcript to `POST /api/escalations`.
6. The backend validates consent, applies rate limiting and sends the transcript to Telegram.
7. The visitor sees a safe confirmation in the chat.

---

## API

```http
POST /api/escalations
```

Request:

```json
{
  "consent_accepted": true,
  "reason": "user_requested_human",
  "transcript": [
    { "role": "user", "content": "When is Alex ready to start work?" },
    { "role": "assistant", "content": "Would you like me to connect him directly?" }
  ],
  "company_website": ""
}
```

Response:

```json
{ "status": "ok" }
```

---

## Security and Privacy Rules

- Do not send the transcript unless the visitor explicitly confirms handoff.
- Do not expose Telegram bot tokens to the frontend.
- Do not log full transcripts in production logs.
- Keep browser-facing errors generic.
- Apply a separate escalation rate limit.
- Treat `company_website` as a honeypot field; if filled, return generic success and do not send.

---

## Required Backend Environment Variables

```text
TELEGRAM_BOT_TOKEN=""
TELEGRAM_OWNER_CHAT_ID=""
ESCALATION_DAILY_LIMIT_PER_IP="3"
ESCALATION_TRANSCRIPT_MAX_MESSAGES="20"
ESCALATION_TRANSCRIPT_MAX_CHARS="8000"
```

`TELEGRAM_OWNER_CHAT_ID` is the private chat id where Alex receives handoff notifications.

---

## Telegram Setup

1. Create a bot through `@BotFather`.
2. Copy the bot token into `TELEGRAM_BOT_TOKEN` in the backend hosting environment.
3. Send `/start` to the bot from Alex's Telegram account.
4. Use `getUpdates` or a temporary helper script to find the private chat id.
5. Put that value into `TELEGRAM_OWNER_CHAT_ID`.
6. Redeploy the backend.
7. Submit a handoff smoke test from `/chat`.

---

## Stage 1 Limitations

- No live Telegram-to-website replies yet.
- No persistent session storage yet.
- No webhook endpoint yet.
- No SSE handoff stream yet.

Those belong to the next stage.
