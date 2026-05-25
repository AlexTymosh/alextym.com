# API Contract

## Purpose

This document defines the backend API contract for `alextym`.

Backend framework:

```text
FastAPI
```

Base path:

```text
/api
```

---

## Endpoints

Required endpoints:

```text
GET  /api/health/live
GET  /api/health/ready
GET  /api/warmup
POST /api/chat
POST /api/chat/stream
POST /api/contact
```

---

## Health: Live

Endpoint:

```text
GET /api/health/live
```

Purpose:

- cheap liveness check;
- keep-alive ping target;
- Koyeb healthcheck target;
- frontend warm-up target.

Must not call:

- OpenAI;
- Qdrant;
- Resend;
- other external APIs.

Response:

```json
{
  "status": "alive"
}
```

---

## Health: Ready

Endpoint:

```text
GET /api/health/ready
```

Purpose:

- readiness check;
- deploy smoke test;
- manual debugging.

May check:

- required env variables;
- Qdrant connection;
- LLM API key presence;
- contact provider configuration.

Should not run expensive LLM generation.

Example response:

```json
{
  "status": "ready",
  "vector_db": "connected",
  "llm_config": "present",
  "contact_email": "configured"
}
```

If not ready:

```json
{
  "status": "not_ready",
  "vector_db": "unavailable",
  "llm_config": "missing",
  "contact_email": "configured"
}
```

Use HTTP 503 for not-ready state.

---

## Warmup

Endpoint:

```text
GET /api/warmup
```

Purpose:

- lightweight backend warm-up;
- initialise clients/config;
- reduce first chat latency.

This endpoint is required for MVP and must be implemented.

Must not:

- generate LLM responses;
- perform expensive operations;
- mutate data.

Example response:

```json
{
  "status": "warmed"
}
```

---

## Chat JSON Fallback

Endpoint:

```text
POST /api/chat
```

Purpose:

- non-streaming chat response;
- fallback if SSE is unstable;
- simpler testing.

Request:

```json
{
  "message": "Tell me about Alex's recent projects",
  "session_id": "optional-session-id"
}
```

Validation:

```text
message: required, 1-2000 characters
session_id: optional, max 100 characters
```

Response:

```json
{
  "answer": "Alex has worked on...",
  "sources": [
    {
      "title": "projects.md",
      "section": "fastapi-saas-template",
      "confidence": "high"
    }
  ],
  "confidence": "medium",
  "not_enough_data": false
}
```

Insufficient-data response:

```json
{
  "answer": "I do not have enough reliable information in Alex's public knowledge base to answer that accurately.",
  "sources": [],
  "confidence": "low",
  "not_enough_data": true
}
```

---

## Chat Streaming

Endpoint:

```text
POST /api/chat/stream
```

Purpose:

- primary endpoint for chat UI;
- Server-Sent Events response;
- display answer progressively.

Content type:

```text
text/event-stream
```

Request:

```json
{
  "message": "Give me your 30-second intro.",
  "session_id": "optional-session-id"
}
```

Suggested SSE events:

```text
event: meta
data: {"request_id":"...", "status":"started"}

event: token
data: {"text":"Alex"}

event: token
data: {"text":" has"}

event: sources
data: {"sources":[{"title":"resume.md","section":"summary","confidence":"high"}]}

event: done
data: {"confidence":"medium","not_enough_data":false}
```

Error event:

```text
event: error
data: {"message":"Something went wrong. Please try again later."}
```

Requirements:

- handle client disconnects;
- do not log full prompts;
- return safe errors;
- support timeout-aware execution.

---

## Contact

Endpoint:

```text
POST /api/contact
```

Purpose:

- receive messages from contact form;
- validate data;
- block simple spam;
- send notification email.

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
email: required, valid email
message: required, 1-4000 characters
company_website: optional honeypot field
```

Honeypot rule:

```text
If company_website is filled, treat as spam.
Return generic success to avoid helping bots.
```

Response:

```json
{
  "status": "ok"
}
```

Do not expose provider errors directly to the user.

---

## Error Handling

Use structured errors.

Minimum format:

```json
{
  "detail": "Human-readable error message"
}
```

Prefer stable, predictable error responses.

Do not return:

- stack traces;
- secrets;
- provider raw errors;
- full prompts;
- internal environment values.

---

## Rate Limiting

Required before public launch:

```text
/api/chat
/api/chat/stream
/api/contact
```

Starting limits:

```text
chat: up to 50 messages per IP per day
contact: 3-5 messages per IP per day
max input length: 2000 chars
max output tokens: configured by model client
```

Implementation note:

```text
Rate limiting is not implemented in Stage 3.
It is tracked as a required pre-public security hardening step and must not be skipped before launch.
```

---

## Testing Requirements

Backend tests should cover:

- `/api/health/live`;
- `/api/health/ready`;
- `/api/warmup`;
- empty chat message;
- too long chat message;
- insufficient-data response;
- prompt injection attempt;
- invalid contact email;
- contact honeypot;
- streaming endpoint basic event format.
