# Deployment

## Deployment goal

Deploy `alextym.com` using low-cost infrastructure while keeping the architecture portable.

Current deployment target:

```text
Frontend: Vercel Free/Hobby
Backend: Render Free
Vector DB: Qdrant Cloud Free
DNS/Registrar: Cloudflare
Email delivery: Resend
Telegram handoff: Telegram Bot API
Temporary handoff state: Upstash Redis TTL
Rate limiting: Upstash Redis when configured, in-memory fallback when unavailable
Keep-alive: UptimeRobot or cron-job.org
```

The source code confirms the Vercel rewrite to the Render backend. DNS provider, hosting tier, Qdrant tier, and keep-alive service are deployment choices outside the application code and must be verified in provider dashboards.

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

Expected DNS setup:

```text
alextym.com      -> Vercel
www.alextym.com  -> Vercel / redirect to apex
```

Recommended Cloudflare mode for Vercel records:

```text
DNS Only / grey cloud
```

Reason:

- Vercel manages its own SSL and edge routing;
- proxying Vercel through Cloudflare can create SSL, redirect, cache, and debugging issues;
- Vercel should own frontend routing and TLS unless there is a deliberate reason to proxy.

Use exact DNS values shown by the Vercel dashboard. Do not hardcode example DNS values.

---

## Frontend deployment

Platform:

```text
Vercel
```

Frontend root:

```text
frontend/
```

Frontend checks after deploy:

```text
/
 /resume
 /chat
 /contact
 /resume/download?detail=concise&sections=experience,education
 /api/health/live via rewrite
 /api/health/ready via rewrite
 /api/warmup via rewrite
```

Frontend code should call local `/api/*` paths. It must not call OpenAI, Qdrant, Resend, Telegram, or Redis directly.

---

## Vercel rewrites

File:

```text
frontend/vercel.json
```

Current production rewrite target:

```text
https://alextym-backend.onrender.com/api/:path*
```

Actual shape:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://alextym-backend.onrender.com/api/:path*"
    }
  ]
}
```

Benefits:

- frontend code does not need to know the backend host;
- production URLs stay clean;
- CORS complexity is reduced;
- backend hosting can be changed by updating the rewrite destination.

Fallback option:

```text
api.alextym.com + strict backend CORS configuration
```

Use this only if Vercel rewrites create timeout, buffering, or SSE instability.

---

## Backend deployment

Current backend platform:

```text
Render
```

Backend root / build context:

```text
repository root
```

Backend must be Docker-ready.

Required files:

```text
content/public/resume.md
backend/Dockerfile
.dockerignore
backend/pyproject.toml
backend/uv.lock
```

The backend must not rely on local persistent storage for production state.

Do not store important production state in:

- local ChromaDB;
- SQLite database on local disk;
- local vector files;
- uploaded private biography;
- generated embeddings on local disk;
- Telegram handoff sessions.

Reason: free / low-cost hosting filesystems are not suitable for important durable state. Temporary handoff state is externalised to Upstash Redis TTL when configured.

---

## Render Free cold-start risk

Render Free can spin down after inactivity.

Risk:

```text
visitor opens chat
  -> frontend calls /api/warmup
  -> Vercel rewrite waits for backend
  -> Render backend cold-starts
  -> first response is delayed
```

Mitigations:

1. External keep-alive monitor:
   - UptimeRobot or cron-job.org;
   - ping `/api/health/live`;
   - interval: 5-15 minutes;
   - optionally limit to expected usage hours.

2. Frontend warm-up:
   - `/chat` calls `/api/warmup` on load;
   - the UI shows a warm-up status;
   - the assistant can still try to respond if warm-up fails.

3. Lightweight backend image:
   - `python:3.12-slim-bookworm`;
   - no heavy local ML libraries;
   - external Qdrant vector store;
   - no local embedding store.

4. Migration fallback:
   - move backend to a paid Render plan or another host if cold starts become unacceptable.

---

## Dockerfile

The current backend Dockerfile uses:

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

COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/app ./app
COPY content/public /content/public

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Do not add system packages unless required.

---

## Backend environment variables

Backend variables currently supported by code:

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
QDRANT_VECTOR_MODE
QDRANT_QUERY_VECTOR_NAME

RAG_TOP_K
RAG_SCORE_THRESHOLD

RESEND_API_KEY
CONTACT_TARGET_EMAIL
CONTACT_FROM_EMAIL

TELEGRAM_BOT_TOKEN
TELEGRAM_OWNER_CHAT_ID
TELEGRAM_WEBHOOK_SECRET
TELEGRAM_WEBHOOK_URL

UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
ESCALATION_SESSION_TTL_SECONDS

HANDOFF_AVAILABILITY_ENABLED
HANDOFF_AVAILABILITY_TIMEZONE
HANDOFF_AVAILABILITY_START
HANDOFF_AVAILABILITY_END

RATE_LIMITING_ENABLED
CHAT_DAILY_LIMIT_PER_IP
CONTACT_DAILY_LIMIT_PER_IP
ESCALATION_DAILY_LIMIT_PER_IP
ESCALATION_MESSAGE_DAILY_LIMIT_PER_IP
```

Default values in code include:

```text
OPENAI_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
OPENAI_MAX_OUTPUT_TOKENS=600
OPENAI_REASONING_EFFORT=low

QDRANT_COLLECTION=alex_public_knowledge
QDRANT_VECTOR_MODE=single
QDRANT_QUERY_VECTOR_NAME=body_dense

RAG_TOP_K=6
RAG_SCORE_THRESHOLD=0.4

RATE_LIMITING_ENABLED=true
CHAT_DAILY_LIMIT_PER_IP=50
CONTACT_DAILY_LIMIT_PER_IP=5
ESCALATION_DAILY_LIMIT_PER_IP=3
ESCALATION_MESSAGE_DAILY_LIMIT_PER_IP=30
ESCALATION_SESSION_TTL_SECONDS=7200

HANDOFF_AVAILABILITY_ENABLED=true
HANDOFF_AVAILABILITY_TIMEZONE=Europe/London
HANDOFF_AVAILABILITY_START=09:00
HANDOFF_AVAILABILITY_END=21:00
```

The committed `.env.example` may intentionally use different starting values for some public limits, for example a higher handoff limit. Production values should be set deliberately in the hosting dashboard.

Rules:

- never commit real `.env`;
- keep `.env.example` current;
- store secrets in the backend hosting provider dashboard;
- do not expose backend secrets through frontend variables;
- do not use `NEXT_PUBLIC_*` for Telegram, Redis, Resend, OpenAI, or Qdrant secrets.

---

## Health and warm-up endpoints

Current endpoints:

```text
GET /api/health/live
GET /api/health/ready
GET /api/warmup
```

Current behaviour:

- `/api/health/live` returns `{"status":"alive"}`;
- `/api/health/ready` returns configuration presence statuses, not real provider connectivity checks;
- `/api/warmup` returns lightweight app/environment readiness metadata;
- none of these endpoints call OpenAI, Qdrant, Resend, Telegram, or Redis.

Current readiness fields:

```text
status
app
environment
vector_db
llm_config
contact_email
```

Current configuration status values:

```text
configured
not_configured
```

---

## Resend setup

Backend variables:

```text
RESEND_API_KEY
CONTACT_TARGET_EMAIL
CONTACT_FROM_EMAIL
```

Rules:

- `CONTACT_FROM_EMAIL` must use a verified Resend sender/domain/subdomain;
- the frontend must never receive `RESEND_API_KEY`;
- the sender address must belong to the verified sending domain;
- the submitter email is used as `reply_to`, not as the sender.

Contact smoke test:

```powershell
$body = @{
  name = "Test User"
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

## Telegram live handoff setup

The visitor stays on `/chat`.

After explicit consent:

```text
frontend sends the current transcript to POST /api/escalations
  -> backend checks availability, honeypot, rate limit, consent, and size limits
  -> backend stores a temporary handoff session in Upstash Redis TTL when configured
  -> backend sends a Telegram control message and transcript
  -> frontend opens GET /api/escalations/{handoff_id}/stream
  -> owner replies in Telegram by replying to a handoff message
  -> Telegram sends the update to POST /api/telegram/webhook
  -> backend validates secret token and owner chat id
  -> backend stores the owner reply in Redis TTL
  -> browser receives the owner reply through SSE
  -> visitor messages during handoff go to POST /api/escalations/{handoff_id}/messages
  -> backend forwards visitor messages to Telegram
```

Required variables:

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
```

Detailed setup:

```text
docs/telegram-handoff-setup.md
```

The Telegram bot token and Upstash token are backend-only secrets.

---

## Qdrant setup

Required variables:

```text
QDRANT_URL
QDRANT_API_KEY
QDRANT_COLLECTION
```

Optional vector-mode variables:

```text
QDRANT_VECTOR_MODE=single
QDRANT_QUERY_VECTOR_NAME=body_dense
```

Supported vector modes:

```text
single
named
```

Named dense vectors supported by code:

```text
title_dense
body_dense
summary_dense
```

Current query vector name default:

```text
body_dense
```

Run generated RAG extraction and ingestion:

```bash
task rag:extract-resume
task rag:ingest:generated
```

Compatibility alias:

```bash
task rag:ingest
```

This alias uses the current generated resume ingestion path. The legacy
`backend/knowledge/` has been removed and must not be reintroduced as a public
knowledge source.

---

## Production smoke checklist

Run after every deployment that touches frontend routing, backend API, provider configuration, or environment variables.

### HTTP checks

```powershell
Invoke-RestMethod "https://alextym.com/api/health/live"
Invoke-RestMethod "https://alextym.com/api/health/ready"
Invoke-RestMethod "https://alextym.com/api/warmup"
```

Expected readiness shape:

```text
status: ready
app: ready
environment: <environment>
vector_db: configured | not_configured
llm_config: configured | not_configured
contact_email: configured | not_configured
```

### Browser checks

```text
/
 /resume
 /chat
 /contact
```

### Functional checks

- ask one AI/RAG chat question;
- verify quick prompts return scripted frontend responses;
- trigger the handoff prompt and verify Telegram receives a control message and transcript;
- confirm the Telegram notification contains a `Handoff ID`;
- reply in Telegram and verify the reply appears in `/chat`;
- send a new visitor message from `/chat` while handoff is active and verify it arrives in Telegram;
- close the handoff from the UI and verify new messages return to AI mode;
- submit a contact form smoke test;
- check Render logs for unexpected 5xx errors;
- check Resend logs if contact delivery fails;
- check Telegram delivery and webhook logs if escalation fails.

---

## Migration path

Backend hosting must be replaceable.

Migration from Render to another backend host should require only:

- deploy the same Docker image;
- copy backend environment variables;
- verify `/api/health/live`;
- verify `/api/health/ready`;
- verify `/api/warmup`;
- verify `/api/chat` and `/api/chat/stream`;
- verify `/api/contact`;
- verify `/api/escalations`;
- verify `/api/escalations/{handoff_id}/stream`;
- verify `/api/escalations/{handoff_id}/messages`;
- verify `/api/escalations/{handoff_id}/close`;
- verify `/api/telegram/webhook`;
- update `frontend/vercel.json` rewrite destination;
- redeploy frontend;
- test chat, contact form, and Telegram live handoff.

No frontend code changes should be required if the `/api/*` contract remains stable.

---

## Deployment checklist

Cloudflare:

- [ ] Use Cloudflare DNS.
- [ ] Keep Vercel records DNS Only unless intentionally testing proxy mode.
- [ ] Verify apex and `www` behaviour.

Vercel:

- [ ] Connect GitHub repository.
- [ ] Use `frontend/` as project root.
- [ ] Verify the frontend build can read root-level `content/public/resume.md`.
      If the platform isolates the frontend root, switch to a repository-root
      build with frontend install/build commands.
- [ ] Add custom domain.
- [ ] Verify `/`, `/resume`, `/chat`, `/contact`.
- [ ] Verify `/resume/download`.
- [ ] Verify `/api/*` rewrites.
- [ ] Verify SSE through rewrite for chat and live handoff.

Render:

- [ ] Deploy backend Docker image from the repository root using `backend/Dockerfile`.
- [ ] Configure backend environment variables.
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

- [ ] Create Qdrant Cloud collection or use configured collection.
- [ ] Configure API key.
- [ ] Set `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION`.
- [ ] Run extraction and ingestion.
- [ ] Test retrieval.

Resend:

- [ ] Verify sending domain/subdomain.
- [ ] Set `RESEND_API_KEY`.
- [ ] Set `CONTACT_TARGET_EMAIL`.
- [ ] Set `CONTACT_FROM_EMAIL`.
- [ ] Smoke test `/api/contact`.

Telegram / Upstash:

- [ ] Create Telegram bot.
- [ ] Start a private chat with the bot.
- [ ] Get `TELEGRAM_OWNER_CHAT_ID`.
- [ ] Set `TELEGRAM_BOT_TOKEN`.
- [ ] Set `TELEGRAM_OWNER_CHAT_ID`.
- [ ] Set `TELEGRAM_WEBHOOK_SECRET`.
- [ ] Set `TELEGRAM_WEBHOOK_URL`.
- [ ] Create Upstash Redis instance.
- [ ] Set `UPSTASH_REDIS_REST_URL`.
- [ ] Set `UPSTASH_REDIS_REST_TOKEN`.
- [ ] Set `ESCALATION_SESSION_TTL_SECONDS`.
- [ ] Register Telegram webhook with the same secret token.
- [ ] Verify `getWebhookInfo`.
- [ ] Smoke test full live handoff.

OpenAI:

- [ ] Set project budget/alerts in OpenAI dashboard.
- [ ] Set `OPENAI_API_KEY`.
- [ ] Keep application rate limits enabled.
- [ ] Verify chat still works after deployment.
