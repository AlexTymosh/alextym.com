# API Contract

## Purpose

This document defines the backend API contract for `alextym.com`.

Backend framework:

```text
FastAPI
```

Base path:

```text
/api
```

The FastAPI app registers routers for:

```text
health
chat
contact
escalation
telegram
```

---

## Implemented endpoints

```text
GET  /api/health/live
GET  /api/health/ready
GET  /api/warmup

POST /api/chat
POST /api/chat/stream

POST /api/contact

POST /api/escalations
POST /api/escalations/{handoff_id}/messages
GET  /api/escalations/{handoff_id}/stream
POST /api/escalations/{handoff_id}/close

POST /api/telegram/webhook
```

---

## Health: live

Endpoint:

```text
GET /api/health/live
```

Purpose:

- cheap liveness check;
- keep-alive ping target;
- deployment smoke test.

Does not call:

- OpenAI;
- Qdrant;
- Resend;
- Telegram;
- Redis / Upstash;
- other external APIs.

Response:

```json
{
  "status": "alive"
}
```

---

## Health: ready

Endpoint:

```text
GET /api/health/ready
```

Purpose:

- configuration readiness check;
- deploy smoke test;
- manual debugging.

Current behaviour:

- checks whether required configuration values are present;
- does not perform live Qdrant/OpenAI/Resend network calls;
- currently returns HTTP 200 with configuration status fields.

Response shape:

```json
{
  "status": "ready",
  "app": "ready",
  "environment": "local",
  "vector_db": "configured",
  "llm_config": "configured",
  "contact_email": "configured"
}
```

Possible field values for provider configuration fields:

```text
configured
not_configured
```

---

## Warmup

Endpoint:

```text
GET /api/warmup
```

Purpose:

- lightweight backend warm-up;
- reduce first chat latency on free / low-cost hosting;
- give frontend a small readiness signal before chat interaction.

This endpoint must not:

- generate LLM responses;
- call Qdrant;
- call Resend;
- call Telegram;
- mutate data.

Response shape:

```json
{
  "status": "warmed",
  "app": "ready",
  "environment": "local"
}
```

---

## Chat JSON fallback

Endpoint:

```text
POST /api/chat
```

Purpose:

- non-streaming chat response;
- frontend fallback if SSE fails before receiving text;
- simpler testing.

Request:

```json
{
  "message": "Tell me about the owner's recent projects",
  "session_id": "optional-session-id",
  "history": [
    {
      "role": "user",
      "content": "Hi"
    },
    {
      "role": "assistant",
      "content": "Hi, I'm the owner's digital assistant."
    }
  ]
}
```

Validation:

```text
message: required, 1-2000 characters
session_id: optional, max 100 characters
history: optional, latest short conversation context
history item role: user or assistant
history item content: 1-2000 characters
history item count: max 10
history total content: max 6000 characters
```

`history` is used only for conversational context, such as pronoun resolution and follow-up understanding. It is not a source of factual claims.

Response:

```json
{
  "answer": "According to the public knowledge base...",
  "sources": [
    {
      "title": "Summary",
      "section": "summary",
      "confidence": "medium"
    }
  ],
  "confidence": "medium",
  "not_enough_data": false,
  "handoff_suggested": false,
  "handoff_reason": null
}
```

Insufficient-data response shape:

```json
{
  "answer": "I do not have enough reliable information in Alex's public knowledge base to answer that accurately.",
  "sources": [],
  "confidence": "low",
  "not_enough_data": true,
  "handoff_suggested": true,
  "handoff_reason": "insufficient_data"
}
```

Out-of-scope questions return a scope-boundary answer rather than a general AI answer. The assistant is focused on the public professional profile, projects, skills, CV, availability, and contact options.

---

## Chat streaming

Endpoint:

```text
POST /api/chat/stream
```

Purpose:

- primary endpoint for typed chat messages;
- Server-Sent Events response;
- progressive answer display in the frontend.

Content type:

```text
text/event-stream
```

Request:

```json
{
  "message": "Give me your 1-minute intro.",
  "session_id": "optional-session-id",
  "history": []
}
```

Current SSE events:

```text
event: meta
data: {"request_id":"...","status":"started"}

event: token
data: {"text":"..."}

event: sources
data: {"sources":[{"title":"Summary","section":"summary","confidence":"medium"}]}

event: done
data: {"request_id":"...","confidence":"medium","not_enough_data":false,"handoff_suggested":false,"handoff_reason":null}
```

Error event:

```text
event: error
data: {"message":"Something went wrong. Please try again later."}
```

Requirements:

- handle client disconnects;
- return safe errors;
- do not expose provider errors;
- do not expose prompts or secrets;
- keep the event format stable for the frontend.

---

## Contact

Endpoint:

```text
POST /api/contact
```

Purpose:

- receive messages from the contact form;
- validate data;
- block simple spam with a honeypot field;
- send notification email through Resend.

Request:

```json
{
  "name": "John Smith",
  "email": "john@example.com",
  "message": "I would like to discuss a role.",
  "company_website": ""
}
```

Validation:

```text
name: required, 1-120 characters
email: required, 3-254 characters, simple email pattern
message: required, 1-4000 characters
company_website: optional honeypot field, max 200 characters
```

Honeypot rule:

```text
If company_website is filled, return generic success and do not send through the normal email path.
```

Success response:

```json
{
  "status": "ok"
}
```

Provider requirements:

```text
RESEND_API_KEY
CONTACT_TARGET_EMAIL
CONTACT_FROM_EMAIL
```

`CONTACT_FROM_EMAIL` must be a Resend-verified sender address. The user-provided email is used as `reply_to`, not as the sender.

Provider failure response:

```json
{
  "detail": "Could not send message. Please try again later."
}
```

HTTP status codes:

```text
503 -> contact form is not configured
502 -> provider delivery failure
```

---

## Escalation: create handoff session

Endpoint:

```text
POST /api/escalations
```

Purpose:

- create a human handoff request after explicit visitor consent;
- send transcript/context to the configured Telegram owner chat;
- create a temporary Redis TTL session when Upstash Redis is configured.

Request:

```json
{
  "consent_accepted": true,
  "reason": "user_requested_human",
  "transcript": [
    {
      "role": "user",
      "content": "Can I speak to the owner?"
    },
    {
      "role": "assistant",
      "content": "Would you like to connect with the owner?"
    }
  ],
  "company_website": ""
}
```

Validation:

```text
consent_accepted: must be true
reason: required, 1-100 characters
transcript: required, 1-20 messages
transcript item role: user or assistant
transcript item content: 1-2000 characters
transcript total content: max 8000 characters
company_website: optional honeypot field, max 200 characters
```

Success response with Redis session storage configured:

```json
{
  "status": "ok",
  "handoff_id": "hnd_...",
  "state": "waiting_for_alex",
  "expires_in_seconds": 7200
}
```

Success response in notification-only mode:

```json
{
  "status": "ok"
}
```

HTTP status codes:

```text
403 -> handoff unavailable outside configured working hours
503 -> escalation is not configured
502 -> Telegram delivery or session storage failure
```

---

## Escalation: visitor message during active handoff

Endpoint:

```text
POST /api/escalations/{handoff_id}/messages
```

Purpose:

- send a visitor follow-up message to Telegram during an active handoff session.

Request:

```json
{
  "content": "I would like to discuss a Python automation role.",
  "company_website": ""
}
```

Validation:

```text
content: required, 1-2000 characters
company_website: optional honeypot field, max 200 characters
```

Success response:

```json
{
  "status": "ok"
}
```

HTTP status codes:

```text
403 -> handoff unavailable
404 -> escalation session was not found
503 -> escalation messaging or session storage is not configured
502 -> Telegram delivery failure
```

---

## Escalation: stream owner messages

Endpoint:

```text
GET /api/escalations/{handoff_id}/stream
```

Purpose:

- open an SSE stream from backend to browser;
- deliver owner replies that arrive through Telegram webhook.

Content type:

```text
text/event-stream
```

Current SSE events:

```text
event: meta
data: {"handoff_id":"hnd_...","status":"connected"}

event: message
data: {"id":"...","role":"alex","content":"...","created_at":"..."}

event: closed
data: {"reason":"session_expired"}

event: closed
data: {"reason":"session_closed"}

: heartbeat
```

The frontend tracks seen message ids to avoid duplicate rendering.

HTTP status codes:

```text
404 -> escalation session was not found
503 -> escalation streaming is not configured
502 -> escalation stream could not be opened
```

---

## Escalation: close handoff session

Endpoint:

```text
POST /api/escalations/{handoff_id}/close
```

Purpose:

- close an active handoff session;
- move the UI back to normal AI chat mode for new messages.

Success response:

```json
{
  "status": "ok",
  "state": "closed"
}
```

HTTP status codes:

```text
404 -> escalation session was not found
503 -> escalation session storage is not configured
502 -> could not close this handoff
```

---

## Telegram webhook

Endpoint:

```text
POST /api/telegram/webhook
```

Purpose:

- receive Telegram updates;
- validate webhook secret token;
- accept replies only from the configured owner chat id;
- store owner replies in the temporary handoff session.

Required header:

```text
X-Telegram-Bot-Api-Secret-Token: <TELEGRAM_WEBHOOK_SECRET>
```

Success response shape:

```json
{
  "status": "ok",
  "handoff_id": "hnd_..."
}
```

Ignored update response shape:

```json
{
  "status": "ignored"
}
```

HTTP status codes:

```text
403 -> invalid Telegram webhook secret
503 -> Telegram webhook is not configured
502 -> Telegram reply could not be processed
```

---

## Error handling

Use structured errors.

Minimum format:

```json
{
  "detail": "Human-readable error message"
}
```

Do not return:

- stack traces;
- secrets;
- provider raw errors;
- full prompts;
- internal environment values;
- private source content.

---

## Rate limiting

Implemented scopes:

```text
chat
contact
escalation
escalation_message
```

Applied to endpoints:

```text
POST /api/chat
POST /api/chat/stream
POST /api/contact
POST /api/escalations
POST /api/escalations/{handoff_id}/messages
```

Current code defaults:

```text
chat: 50 requests per IP per day
contact: 5 requests per IP per day
escalation: 3 requests per IP per day
escalation_message: 30 requests per IP per day
```

The committed `.env.example` may set different starting values for production-like local configuration.

Implementation:

```text
If Upstash Redis REST URL and token are configured:
  -> Redis-backed daily rate limiting is used.

If one Upstash value is missing:
  -> Redis limiter is treated as misconfigured and the API layer falls back to in-memory rate limiting.

If both Upstash values are empty:
  -> in-memory process-local limiter is used.
```

Rate-limit failure response:

```json
{
  "detail": "Daily request limit reached. Please try again later."
}
```

HTTP status:

```text
429
```

---

## Testing requirements

Backend tests should cover:

- `/api/health/live`;
- `/api/health/ready`;
- `/api/warmup`;
- empty chat message;
- too long chat message;
- insufficient-data response;
- prompt injection attempt;
- unsupported-language handling;
- invalid contact email;
- contact honeypot;
- streaming endpoint event format;
- escalation consent validation;
- escalation honeypot;
- active handoff message forwarding;
- missing handoff session;
- Telegram webhook secret validation;
- Telegram ignored update behaviour.

Frontend E2E checks should cover:

- navigation;
- theme toggle;
- resume filters;
- dynamic resume download route;
- chat quick prompts;
- typed chat stream/fallback behaviour;
- handoff prompt;
- closing a handoff session.
