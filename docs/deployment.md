# Deployment

## Deployment Goal

Deploy `alextym` using low-cost infrastructure while keeping the architecture portable.

Initial target:

```text
Frontend: Vercel Free/Hobby
Backend: Koyeb Free
Vector DB: Qdrant Cloud Free
DNS/Registrar: Cloudflare
Keep-alive: UptimeRobot or cron-job.org
```

---

## Domain and DNS

Planned domain:

```text
alextym.com
```

Registrar:

```text
Cloudflare Registrar
```

DNS provider:

```text
Cloudflare DNS
```

Important rule:

```text
Vercel DNS records must be DNS Only / grey cloud.
Do not proxy Vercel records through Cloudflare orange cloud.
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

Use exact DNS values shown by Vercel dashboard. Do not hardcode DNS values from examples.

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
/api/warmup via rewrite
```

---

## Backend Deployment

Initial platform:

```text
Koyeb Free
```

Backend must be Docker-ready.

Required files:

```text
backend/Dockerfile
backend/.dockerignore
backend/uv.lock
```

The backend must not rely on local persistent storage.

Do not store:

- local ChromaDB;
- SQLite database for important state;
- local vector files;
- uploaded private biography;
- generated embeddings on local disk.

---

## Vercel Rewrites

Frontend should call local `/api/*` paths.

Vercel should proxy those requests to the backend.

File:

```text
frontend/vercel.json
```

Example:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://YOUR-KOYEB-APP.koyeb.app/api/:path*"
    }
  ]
}
```

Benefits:

- frontend code does not know backend host;
- easier migration from Koyeb to Railway/Render/Fly.io;
- fewer CORS issues;
- cleaner production URLs.

Fallback:

```text
api.alextym.com + strict CORS
```

Use fallback if Vercel rewrites cause timeout, buffering, or unstable SSE streaming.

---

## Koyeb Free Cold-Start Risk

Koyeb Free can scale to zero after inactivity.

Risk:

```text
User opens chat
-> Vercel rewrite waits for backend
-> Koyeb backend cold-starts
-> response is delayed
-> request may timeout or UX becomes bad
```

Mitigations:

1. Keep-alive monitor:
   - UptimeRobot or cron-job.org;
   - ping `/api/health/live`;
   - interval: 5-15 minutes.

2. Frontend warm-up:
   - when chat page loads, call `/api/warmup`;
   - do not block the UI;
   - show a small warm-up state if useful.

3. Lightweight Docker image:
   - use `python:3.11-slim`;
   - avoid heavy ML libraries;
   - keep startup fast;
   - externalise vector DB.

4. Migration fallback:
   - move backend to Railway/Render/Fly.io if Koyeb Free is unstable.

---

## Docker Requirements

Minimal backend Dockerfile:

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

QDRANT_URL
QDRANT_API_KEY
QDRANT_COLLECTION

RESEND_API_KEY
CONTACT_TARGET_EMAIL

RATE_LIMITING_ENABLED
CHAT_DAILY_LIMIT_PER_IP
```

Starting chat limit:

```text
CHAT_DAILY_LIMIT_PER_IP=50
```

Rules:

- never commit real `.env`;
- keep `.env.example`;
- store secrets in hosting provider dashboard;
- do not expose backend secrets through Next.js public variables.

---

## Migration Path

Backend hosting must be replaceable.

Migration from Koyeb to Railway/Render/Fly.io should require only:

- deploy same Docker image;
- copy environment variables;
- verify `/api/health/live`;
- verify `/api/warmup`;
- update `frontend/vercel.json` rewrite destination;
- redeploy frontend;
- test chat and contact form.

No frontend code changes should be required.

---

## Deployment Checklist

Cloudflare:

- [ ] Buy `alextym.com`.
- [ ] Use Cloudflare DNS.
- [ ] Keep Vercel records DNS Only.
- [ ] Do not enable orange cloud for Vercel records.

Vercel:

- [ ] Connect GitHub repository.
- [ ] Use `frontend/` as project root.
- [ ] Add custom domain.
- [ ] Verify `/`, `/resume`, `/contact`.
- [ ] Verify `/chat`.
- [ ] Verify `/api/*` rewrites.

Koyeb:

- [ ] Deploy backend Docker image.
- [ ] Configure env variables.
- [ ] Verify `/api/health/live`.
- [ ] Verify `/api/warmup`.
- [ ] Verify logs.
- [ ] Test cold-start behaviour.

UptimeRobot / cron-job.org:

- [ ] Monitor `/api/health/live`.
- [ ] Use 5-15 minute interval.
- [ ] Confirm backend stays warm enough.

Qdrant:

- [ ] Create free cluster.
- [ ] Create collection.
- [ ] Configure API key.
- [ ] Run ingestion.
- [ ] Test retrieval.
