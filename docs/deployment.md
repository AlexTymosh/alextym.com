# Deployment

## Deployment Goal

Deploy `alextym` using low-cost infrastructure while keeping the architecture portable.

Current production target:

```text
Frontend: Vercel Free/Hobby
Backend: Render Free
Vector DB: Qdrant Cloud Free
DNS/Registrar: Cloudflare
Email delivery: Resend
Telegram handoff: Telegram Bot API
Keep-alive: UptimeRobot or cron-job.org
```

---

## Domain and DNS

Production domain:

```text
alextym.com
```

Registrar / DNS provider:

```text
Cloudflare
```

Important rule:

```text
Vercel DNS records must be DNS Only / grey cloud.
Do not proxy Vercel records through Cloudflare orange cloud unless there is a specific reason.
```

Reason:

- Vercel manages its own SSL and edge network;
- Cloudflare proxy in front of Vercel can create SSL, redirect, cache, and debugging problems;
- Vercel should own frontend routing and TLS.

Expected DNS setup:

```text
alextym.com      -> Vercel
www.alextym.com  -> Vercel / redirect to apex
```

Use exact DNS values shown by the Vercel dashboard. Do not hardcode DNS values from examples.

---

## Frontend Deployment

Platform:

```text
Vercel
```

Frontend root:

```text
frontend/
```

Required checks after deploy:

```text
/
/resume
/chat
/contact
/api/health/live via rewrite
/api/health/ready via rewrite
/api/warmup via rewrite
```

Frontend code should call local `/api/*` paths. The frontend must not call provider APIs directly.

---

## Backend Deployment

Current platform:

```text
Render Free
```

Backend root / build context:

```text
backend/
```

Backend must be Docker-ready.

Required files:

```text
backend/Dockerfile
backend/.dockerignore
backend/pyproject.toml
backend/uv.lock
```

The backend must not rely on local persistent storage.

Do not store important production state in:

- local ChromaDB;
- SQLite database on local disk;
- local vector files;
- uploaded private biography;
- generated embeddings on local disk;
- Telegram handoff sessions.

Reason: free hosting local filesystems are not suitable for important durable state. Use external storage for future live handoff sessions.

---

## Vercel Rewrites

Frontend should call local `/api/*` paths.

Vercel should proxy those requests to the backend.

File:

```text
frontend/vercel.json
```

Current production rewrite target:

```text
https://alextym-backend.onrender.com/api/:path*
```

Example shape:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-BACKEND-HOST/api/:path*"
    }
  ]
}
```

Benefits:

- frontend code does not know backend host;
- easier migration from Render to Railway/Fly.io/another backend host;
- fewer CORS issues;
- cleaner production URLs.

Fallback:

```text
api.alextym.com + strict CORS
```

Use fallback if Vercel rewrites cause timeout, buffering, or unstable SSE streaming.

---

## Render Free Cold-Start Risk

Render Free can spin down after inactivity.

Risk:

```text
User opens chat
-> Vercel rewrite waits for backend
-> Render backend cold-starts
-> response is delayed
-> request may timeout or UX becomes bad
```

Mitigations:

1. Keep-alive monitor:
   - UptimeRobot or cron-job.org;
   - ping backend `/api/health/live`;
   - interval: 5-15 minutes;
   - schedule may be limited to expected working hours.

2. Frontend warm-up:
   - when chat page loads, call `/api/warmup`;
   - do not block the UI;
   - show a small warm-up state.

3. Lightweight Docker image:
   - use `python:3.12-slim-bookworm`;
   - avoid heavy ML libraries;
   - keep startup fast;
   - externalise vector DB.

4. Migration fallback:
   - move backend to a paid Render plan or another host if cold-start behaviour becomes unacceptable.

---

## Docker Requirements

Minimal backend Dockerfile pattern:

```dockerfile
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY app ./app

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Do not add system packages unless required.

---

## Environment Variables

Backend variables:

```text
APP_NAME
ENVIRONMENT
FRONTEND_ORIGIN

OPENAI_API_KEY
OPENAI_MODEL
OPENAI_EMBEDDING_MODEL
OPENAI_EMBEDDING_DIMENSIONS
OPENAI_MAX_OUTPUT_TOKENS
OPENAI_REASONING_EFFORT

QDRANT_URL
QDRANT_API_KEY
QDRANT_COLLECTION

RAG_TOP_K
RAG_SCORE_THRESHOLD

RESEND_API_KEY
CONTACT_TARGET_EMAIL
CONTACT_FROM_EMAIL

TELEGRAM_BOT_TOKEN
TELEGRAM_OWNER_CHAT_ID

RATE_LIMITING_ENABLED
CHAT_DAILY_LIMIT_PER_IP
CONTACT_DAILY_LIMIT_PER_IP
ESCALATION_DAILY_LIMIT_PER_IP
ESCALATION_TRANSCRIPT_MAX_MESSAGES
ESCALATION_TRANSCRIPT_MAX_CHARS
```

Starting limits:

```text
CHAT_DAILY_LIMIT_PER_IP=50
CONTACT_DAILY_LIMIT_PER_IP=5
ESCALATION_DAILY_LIMIT_PER_IP=10
ESCALATION_TRANSCRIPT_MAX_MESSAGES=50
ESCALATION_TRANSCRIPT_MAX_CHARS=8000
```

Rules:

- never commit real `.env`;
- keep `.env.example` current;
- store secrets in the hosting provider dashboard;
- do not expose backend secrets through Next.js public variables;
- do not use `NEXT_PUBLIC_*` for Telegram or provider secrets.

---

## Resend Setup

Backend variables:

```text
RESEND_API_KEY
CONTACT_TARGET_EMAIL
CONTACT_FROM_EMAIL
```

Rules:

- `CONTACT_FROM_EMAIL` must use a verified Resend domain or subdomain;
- frontend must not receive the Resend API key;
- sender address must belong to the verified sending domain;
- submitter email may be used as `reply_to`, not as the sender address.

Smoke test:

```powershell
$body = @{
  name = "Alex Test"
  email = "test@example.com"
  message = "Contact form smoke test."
  company_website = ""
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "https://alextym.com/api/contact" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

---

## Telegram Handoff Setup

Current stage:

```text
Notification-only handoff.
```

The visitor stays on `/chat`. After explicit consent, the frontend sends the current transcript to:

```text
POST /api/escalations
```

The backend sends a Telegram notification to the configured owner chat.

Required variables:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_OWNER_CHAT_ID
ESCALATION_DAILY_LIMIT_PER_IP
ESCALATION_TRANSCRIPT_MAX_MESSAGES
ESCALATION_TRANSCRIPT_MAX_CHARS
```

Setup details:

```text
docs/telegram-handoff-setup.md
```

Smoke test:

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
A Telegram notification is delivered to the configured owner chat.
```

---

## Production Smoke Checklist

Run after every deployment that touches frontend routing, backend API, provider configuration, or environment variables.

### HTTP checks

```powershell
Invoke-RestMethod "https://alextym.com/api/health/live"
Invoke-RestMethod "https://alextym.com/api/health/ready"
Invoke-RestMethod "https://alextym.com/api/warmup"
```

Expected readiness:

```text
status: ready
vector_db: configured
llm_config: configured
contact_email: configured
```

### Browser checks

```text
/
/resume
/chat
/contact
```

### Functional checks

- ask one chat question;
- trigger the handoff prompt and verify Telegram notification;
- submit a contact form smoke test;
- check Render logs for unexpected 5xx errors;
- check Resend logs if contact delivery fails;
- check Telegram delivery if escalation fails.

---

## Migration Path

Backend hosting must be replaceable.

Migration from Render to Railway/Fly.io/another backend host should require only:

- deploy the same Docker image;
- copy environment variables;
- verify `/api/health/live`;
- verify `/api/health/ready`;
- verify `/api/warmup`;
- update `frontend/vercel.json` rewrite destination;
- redeploy frontend;
- test chat, contact form, and Telegram handoff.

No frontend code changes should be required.

---

## Deployment Checklist

Cloudflare:

- [ ] Use Cloudflare DNS.
- [ ] Keep Vercel records DNS Only.
- [ ] Do not enable orange cloud for Vercel records unless intentionally tested.

Vercel:

- [ ] Connect GitHub repository.
- [ ] Use `frontend/` as project root.
- [ ] Add custom domain.
- [ ] Verify `/`, `/resume`, `/contact`.
- [ ] Verify `/chat`.
- [ ] Verify `/api/*` rewrites.

Render:

- [ ] Deploy backend Docker image from `backend/`.
- [ ] Configure env variables.
- [ ] Verify `/api/health/live`.
- [ ] Verify `/api/health/ready`.
- [ ] Verify `/api/warmup`.
- [ ] Verify logs.
- [ ] Test cold-start behaviour.

UptimeRobot / cron-job.org:

- [ ] Monitor backend `/api/health/live`.
- [ ] Use 5-15 minute interval.
- [ ] Confirm backend stays warm enough during expected usage hours.

Qdrant:

- [ ] Create free cluster.
- [ ] Configure API key.
- [ ] Set `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION`.
- [ ] Run ingestion.
- [ ] Test retrieval.

Resend:

- [ ] Verify sending domain/subdomain.
- [ ] Set `RESEND_API_KEY`.
- [ ] Set `CONTACT_TARGET_EMAIL`.
- [ ] Set `CONTACT_FROM_EMAIL`.
- [ ] Test `/api/contact`.

Telegram:

- [ ] Create bot with BotFather.
- [ ] Send `/start` to the bot.
- [ ] Set `TELEGRAM_BOT_TOKEN`.
- [ ] Set `TELEGRAM_OWNER_CHAT_ID`.
- [ ] Test `/api/escalations`.
