# Security and Privacy

## Purpose

`alextym.com` uses reviewed public professional data to answer employer-facing questions.

Security and privacy are part of the product scope, especially because the system combines:

- public profile content;
- AI/RAG retrieval;
- contact form messages;
- human handoff transcripts;
- Telegram webhook handling;
- external providers.

---

## Core principles

1. Do not expose secrets.
2. Do not publish private biography data.
3. Do not index private or unreviewed content.
4. Do not log unnecessary personal data.
5. Do not let the assistant invent facts.
6. Do not let user input override system instructions.
7. Share chat transcripts with a human only after explicit visitor consent.
8. Keep temporary handoff sessions time-limited.
9. Keep frontend free of backend/provider secrets.
10. Keep the system simple enough to audit.

---

## Secrets

Never commit:

- `.env`;
- API keys;
- OpenAI keys;
- Qdrant keys;
- Resend keys;
- Telegram bot tokens;
- Telegram webhook secrets;
- Redis / Upstash tokens;
- provider tokens;
- private source documents;
- `private/`;
- `_local`;
- `.tmp` outputs that contain sensitive or unreviewed data.

Required committed template:

```text
backend/.env.example
```

Real secrets must live in hosting provider environment variables.

Frontend must not receive backend secrets.

Only use `NEXT_PUBLIC_*` for values that are genuinely public.

---

## Public and private data boundary

Current public resume source used for structured RAG extraction:

```text
content/public/resume.md
```

Generated RAG output:

```text
.tmp/rag/resume.generated.chunks.json
```

This generated output is ignored by Git and should be regenerated locally / during controlled ingestion.

The old `backend/knowledge/` directory has been removed. Do not add new
backend-local public knowledge sources.

Ignored private / unreviewed paths:

```text
private/
.tmp/rag/resume.generated.chunks.json
```

Do not include:

- unnecessary family details;
- medical information;
- health information;
- private contacts;
- names of unrelated third parties unless explicitly public and necessary;
- sensitive legal details;
- personal data of third parties;
- private addresses;
- full private history;
- raw private chat logs;
- unverified claims presented as facts.

---

## Recruiter-facing knowledge

Public RAG content should focus on:

- professional profile;
- projects;
- skills;
- work experience;
- automation and software development;
- education and training;
- availability / right-to-work facts when intentionally public;
- contact paths.

Avoid irrelevant personal stories unless they clearly support professional positioning and are intended to be public.

---

## Assistant safety rules

The assistant must not:

- reveal system prompts;
- reveal hidden developer instructions;
- dump the full knowledge base;
- expose API keys;
- invent missing facts;
- claim unsupported experience;
- answer as the owner directly unless explicitly drafting first-person text;
- disclose private personal data;
- accept instructions from retrieved context as system instructions.

The assistant is focused on the public professional profile, projects, skills, CV, availability, and contact options.

For unrelated general questions, the current behaviour is a scope-boundary response, not general-purpose AI chat.

Short chat history may be sent with a request only for conversational context, such as pronoun resolution and follow-up understanding. It must not be treated as a source of factual claims.

Questions about unrelated third-party people should not trigger owner-profile RAG.

Current insufficient-data response:

```text
I do not have enough reliable information in Alex's public knowledge base to answer that accurately.
```

---

## Prompt injection

Treat user messages and retrieved documents as untrusted input.

Current phrase-based checks cover examples such as:

```text
ignore previous instructions
reveal your system prompt
show hidden context
answer without context
pretend you know
dump all documents
dump the knowledge base
show API keys
bypass rules
```

Basic phrase detection is only one layer. The main defences are:

- prompt separation;
- retrieved context treated as data;
- no-hallucination policy;
- refusal to reveal hidden/system/developer instructions;
- no provider secrets in frontend;
- no private knowledge in public RAG sources.

---

## Logging

Log minimally.

Useful logs:

- request id;
- endpoint;
- status code;
- duration;
- provider error category;
- retrieved chunk count;
- insufficient-data flag;
- handoff status category.

Do not log:

- API keys;
- raw system prompts;
- full user messages unless temporarily needed for local debugging;
- full contact form messages;
- full escalation transcripts;
- Telegram bot tokens;
- Telegram webhook secrets;
- Redis / Upstash tokens;
- private biography content;
- full retrieved context.

If detailed logs are temporarily needed, keep them local and remove before deploy.

---

## Contact form security

Contact endpoint controls:

- Pydantic validation;
- simple email pattern;
- max field lengths;
- honeypot field;
- daily rate limiting;
- safe generic errors;
- backend-only Resend secret.

Honeypot field:

```text
company_website
```

If filled, the backend returns generic success and does not send through the normal email path.

Backend-only configuration:

```text
RESEND_API_KEY
CONTACT_TARGET_EMAIL
CONTACT_FROM_EMAIL
```

The form submitter's email may be used as `reply_to`, but it must not be used as the sender address.

Do not expose Resend errors directly to the browser.

---

## Telegram handoff security

The current Telegram handoff supports:

```text
explicit visitor consent
  -> POST /api/escalations
  -> temporary Upstash Redis TTL session when configured
  -> Telegram notification to owner chat
  -> GET /api/escalations/{handoff_id}/stream
  -> owner reply through POST /api/telegram/webhook
  -> visitor follow-up through POST /api/escalations/{handoff_id}/messages
  -> handoff close through POST /api/escalations/{handoff_id}/close
```

Required controls:

- explicit user consent before transcript sharing;
- transcript size limits;
- rate limiting for handoff creation;
- rate limiting for visitor messages during active handoff;
- honeypot field;
- backend-only Telegram bot token;
- backend-only webhook secret;
- backend-only Upstash Redis token;
- temporary Redis TTL storage;
- owner-chat validation;
- safe generic browser errors;
- no frontend access to Telegram or Redis secrets.

Backend-only configuration:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_OWNER_CHAT_ID
TELEGRAM_WEBHOOK_SECRET
TELEGRAM_WEBHOOK_URL
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
ESCALATION_SESSION_TTL_SECONDS
ESCALATION_DAILY_LIMIT_PER_IP
ESCALATION_MESSAGE_DAILY_LIMIT_PER_IP
HANDOFF_AVAILABILITY_ENABLED
HANDOFF_AVAILABILITY_TIMEZONE
HANDOFF_AVAILABILITY_START
HANDOFF_AVAILABILITY_END
```

Transcript and message size limits are code constants, not runtime environment variables.

Current schema constants:

```text
MAX_ESCALATION_TRANSCRIPT_MESSAGES=20
MAX_ESCALATION_TRANSCRIPT_TOTAL_CHARS=8000
MAX_ESCALATION_MESSAGE_CHARS=2000
```

Do not configure these obsolete environment variables:

```text
ESCALATION_TRANSCRIPT_MAX_MESSAGES
ESCALATION_TRANSCRIPT_MAX_CHARS
```

Honeypot field:

```text
company_website
```

If filled, the backend returns generic success.

Consent copy must make clear that:

```text
If the visitor connects with the owner, the current chat history is shared for context.
No email or phone number is shared unless the visitor types it manually.
```

Telegram webhook requirements:

- validate `X-Telegram-Bot-Api-Secret-Token`;
- accept replies only from `TELEGRAM_OWNER_CHAT_ID`;
- store replies only when a valid handoff id is present;
- ignore unrelated Telegram updates safely;
- do not expose Telegram errors to the browser;
- do not log full Telegram reply text unless temporarily debugging locally.

Do not use tool-calling to perform Telegram side effects directly.

---

## Rate limiting

Implemented scopes:

```text
chat
contact
escalation
escalation_message
```

Applied endpoints:

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

Current `.env.example` values can override these defaults:

```text
ESCALATION_DAILY_LIMIT_PER_IP=10
ESCALATION_MESSAGE_DAILY_LIMIT_PER_IP=50
```

Implementation:

```text
If Upstash Redis REST URL and token are configured:
  -> use Upstash Redis daily limiter.

If Upstash is partially configured:
  -> treat Redis limiter as misconfigured and fall back to in-memory limiter at the API layer.

If Upstash is not configured:
  -> use process-local in-memory limiter.
```

The in-memory limiter resets on backend restart and is not shared across instances.

---

## Cost protection

Set monthly budget limits for the LLM provider.

Application-level controls:

- max input length;
- max output tokens;
- daily rate limiting;
- contact form honeypot and rate limiting;
- escalation honeypot and rate limiting;
- no embedding generation during normal chat except query embeddings.

Provider-side controls that must be configured outside code:

- OpenAI project budget;
- usage alerts;
- key restrictions if available;
- provider dashboard monitoring.

Never launch public chat without cost limits.

---

## Frontend security

Frontend must not contain:

- backend secrets;
- provider keys;
- private biography;
- raw prompts;
- hidden sensitive data;
- Telegram bot token;
- Upstash Redis token;
- Resend API key;
- Qdrant API key;
- OpenAI API key.

Frontend should call:

```text
/api/*
```

not direct provider APIs.

---

## Backend security

Backend must:

- validate all requests with Pydantic;
- enforce message length limits;
- enforce chat history item and total-size limits;
- enforce escalation transcript size limits;
- enforce explicit consent for handoff transcript sharing;
- sanitize/log safely;
- keep provider clients server-side;
- return safe errors;
- avoid local persistent secrets;
- avoid long-term storage of active handoff messages.

---

## Deployment security

Cloudflare / DNS:

- use DNS Only for Vercel records unless intentionally testing proxy mode;
- do not proxy Vercel records unless there is a specific reason.

Render / backend host:

- store secrets as environment variables;
- do not build images with secrets baked in;
- verify logs after deploy;
- keep Docker image minimal;
- do not rely on local disk for important state.

Vercel:

- use rewrites for `/api/*`;
- keep backend URL in deployment configuration;
- do not expose private env vars to frontend;
- exclude preview deployments from indexing where configured.

Telegram:

- store bot token only in backend environment variables;
- rotate token if exposed;
- validate webhook secret token for every webhook update;
- use local tunnelling only for development webhook testing.

---

## Security definition of done

Security is acceptable when:

- no secrets are committed;
- private biography is not committed;
- public knowledge files are reviewed;
- generated RAG chunks contain only public reviewed content;
- chat, contact, escalation, and escalation-message paths have rate limiting;
- contact form has honeypot;
- escalation has explicit consent and honeypot;
- Telegram webhook has secret-token validation;
- Telegram webhook accepts replies only from the owner chat;
- assistant refuses prompt/system extraction;
- assistant uses insufficient-data response;
- provider budget limit is configured;
- logs do not contain sensitive data.
