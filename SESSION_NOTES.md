# SESSION_NOTES.md

## Purpose

A working map of the current project state for Codex.

This file does not replace `README.md` or `AGENTS.md`.

- `README.md` — project description for people.
- `AGENTS.md` — stable rules for Codex.
- `SESSION_NOTES.md` — current status, nearest plan, risks, and Definition of Done.

Keep the file short. Move architecture, deployment, and RAG details to `docs/`.

---

## Project goal

Create a personal AI portfolio website for Alex.

The website must include a page with an AI chat that answers employers’ questions about Alex’s professional profile, projects, skills, and experience based on a RAG knowledge base.

The website must demonstrate:

- frontend on Next.js;
- backend on FastAPI;
- RAG pipeline;
- streaming chat;
- privacy-aware handling of biography;
- deploy-ready architecture.

---

## Current product concept

Main pages:

```text
/          -> home page
/resume    -> web resume + download CV
/chat      -> AI chat
/contact   -> contact form + GitHub/LinkedIn links
```

Menu:

```text
Home
Resume
Chat
```

`/contact` remains a public page and is linked from the Connect block, but it is not shown in the top pill menu.

Home page:

```text
A separate simple page. Final content will be specified by a separate example.
```

Chat page intro:

```text
Hi, I'm Alex's digital assistant.
This AI is augmented by my work and experiences.
Ask me about my RAG projects or AI automation workflows.
```

Quick prompts:

```text
Summarize Alex's professional profile.
Tell me about Alex's FastAPI and backend experience.
Tell me about Alex's AI-assisted development and RAG-based systems.
```

---

## Approved architecture v1

```text
Frontend: Next.js + TypeScript + Tailwind CSS
Frontend hosting: Vercel Free/Hobby

Backend: FastAPI + Pydantic
Backend hosting v1: Koyeb Free
Backend fallback: Railway / Render / Fly.io

Vector DB: Qdrant Cloud Free
Email: Resend Free
LLM: OpenAI/OpenRouter with budget limit

Domain: alextym.com
Registrar/DNS: Cloudflare
Vercel DNS records: DNS Only, not proxied
```

Routing v1:

```text
Frontend calls /api/*
Vercel rewrites /api/* -> Koyeb backend
```

Fallback routing:

```text
api.alextym.com + strict CORS
```

Use fallback only if Vercel rewrites break SSE streaming or cause timeout/proxy issues.

---

## Important architectural decisions

1. Do not do fine-tuning. Use RAG.
2. Do not store the vector DB inside the backend container.
3. Do not commit the private biography or any private or personalised data.
4. Current committed public RAG source:
   - `backend/knowledge/resume.md`
5. Do not commit `backend/knowledge/biography_public.md` or `backend/knowledge/projects.md` at this stage.
6. Use ignored local drafts under `private/knowledge/` for private source notes.
7. The Assistant answers as Alex’s digital assistant, not directly as Alex.
8. If the data is insufficient, the Assistant must say that the data is insufficient.
9. Chat must have a streaming endpoint and a JSON fallback.
10. Backend must be portable via Docker.
11. Koyeb Free can be used only with the cold-start risk taken into account.
12. Use lightweight `/api/health/live` for keep-alive.
13. `/api/warmup` must be implemented as a lightweight endpoint for warming up the backend.

---

## Required backend endpoints

```text
GET  /api/health/live
GET  /api/health/ready
GET  /api/warmup
POST /api/chat
POST /api/chat/stream
POST /api/contact
```

Rules:

- `/api/health/live` — a lightweight endpoint for keep-alive, with no external API calls.
- `/api/health/ready` — checks env/config and the availability of important dependencies.
- `/api/warmup` — required lightweight warm-up endpoint.
- `/api/chat` — JSON fallback.
- `/api/chat/stream` — main SSE endpoint for the UI.
- `/api/contact` — contact form with validation, honeypot, and rate limiting.

---

## Koyeb Free risk

Risk:

```text
Koyeb Free may move the backend into sleep mode.
The first request after sleep may be slow.
Vercel rewrites may return timeout/504.
```

Mitigations:

- UptimeRobot or cron-job.org pings `/api/health/live` every 5–15 minutes.
- The frontend makes a silent warm-up request when the chat page loads.
- Docker image must be lightweight.
- Do not pull heavy ML libraries unless necessary.
- If unstable, move the backend to Railway/Render/Fly.io.

---

## Target structure

```text
alextym/
├─ frontend/
│  ├─ app/
│  │  ├─ page.tsx
│  │  ├─ resume/page.tsx
│  │  ├─ chat/page.tsx
│  │  ├─ contact/page.tsx
│  │  └─ layout.tsx
│  ├─ components/
│  ├─ public/resume/
│  ├─ vercel.json
│  └─ package.json
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ rag/
│  │  ├─ llm/
│  │  └─ core/
│  ├─ knowledge/
│  ├─ scripts/
│  ├─ tests/
│  ├─ Dockerfile
│  ├─ .dockerignore
│  ├─ .env.example
│  └─ pyproject.toml
├─ docs/
├─ scripts/
├─ README.md
├─ AGENTS.md
├─ SESSION_NOTES.md
├─ Taskfile.yml
└─ .gitignore
```

---

## Nearest task for Codex

Complete only the first technical stage. Do not try to implement the entire RAG immediately.

### Stage 1 — align the skeleton with the current architecture

Do:

- add `backend/Dockerfile`;
- add `backend/.dockerignore`;
- add `frontend/vercel.json`;
- add folders:
  - `backend/app/services/`
  - `backend/app/llm/`
- update health routes:
  - `/api/health/live`
  - `/api/health/ready`
  - `/api/warmup`
- add or update basic schemas;
- add minimal tests for health endpoints;
- make sure the backend starts locally;
- make sure the Docker build passes.
- add the `_local` folder to `.gitignore`.

Do not do yet:

- full Qdrant ingestion;
- production LLM integration;
- Resend integration;
- paid hosting setup;
- auth/users/admin panel.

---

## Definition of Done for Stage 1

Stage 1 is ready if:

- `backend` starts locally;
- `GET /api/health/live` returns `{"status": "alive"}`;
- `GET /api/health/ready` returns a structured readiness response;
- `GET /api/warmup` returns a lightweight warm-up response;
- `/api/health/live` makes no external API calls;
- Dockerfile builds the backend image;
- `frontend/vercel.json` contains a rewrite placeholder;
- health endpoint tests pass;
- README or SESSION_NOTES is updated according to the actual changes;
- private data and secrets are not added to the repo.

---

## Next stages after Stage 1

### Stage 2 — frontend chat shell

- separate `/chat` page with chat UI;
- quick prompts;
- reset chat;
- frontend warm-up call;
- loading/error states;
- fallback mock response.

### Stage 3 — backend chat service

- thin router;
- `ChatService`;
- `/api/chat`;
- `/api/chat/stream`;
- insufficient-data response;
- basic prompt injection guard.

### Stage 4 — RAG

- public knowledge files;
- chunker;
- metadata;
- embeddings;
- Qdrant ingestion;
- retriever;
- prompt builder.

### Stage 5 — contact form

- validation;
- honeypot;
- rate limiting;
- Resend or mock provider;
- frontend success/error states.

### Stage 6 — deploy docs

- Vercel;
- Koyeb;
- Cloudflare DNS Only;
- UptimeRobot keep-alive;
- Qdrant setup;
- env variables.

---

## Minimal project tests

Backend:

- health live;
- health ready;
- empty chat message;
- too long chat message;
- insufficient-data response;
- prompt injection attempt;
- contact invalid email;
- contact honeypot;
- chunk metadata.

Frontend:

- build passes;
- `/` renders;
- `/resume` renders;
- `/chat` renders;
- `/contact` renders.

---

## MVP prohibitions

Do not do:

- Keycloak;
- user accounts;
- admin panel;
- CMS;
- blog;
- fine-tuning;
- SaaS architecture;
- paid tiers unless necessary;
- local ChromaDB in the container;
- publication of the private biography;
- adding to GitHub and/or the project health information, personal contacts, names of colleagues, friends, managers, and any other private or personalised data;
- mentioning external sources of inspiration in the UI/README;
- do not overcomplicate the architecture unnecessarily.


---

## Current status

Architecture agreed. Stage 1, Stage 2, Stage 3 and Stage 4 have been implemented.

Chosen path:

```text
Vercel frontend
Koyeb Free backend
Qdrant Cloud Free
Vercel rewrites
UptimeRobot keep-alive
SSE streaming + JSON fallback
Cloudflare DNS Only for Vercel records
```

Done in Stage 1:

```text
backend FastAPI skeleton
frontend Next.js skeleton
Dockerfile
health endpoints
warmup endpoint
vercel.json rewrite placeholder
basic health tests
.gitignore with _local/
backend Python dependency workflow migrated to uv
backend/uv.lock and backend/.python-version added
CI, Dockerfile, README and deployment docs use uv for backend
root Taskfile.yml added for ci, format, dev, smoke and stop commands
Taskfile smoke/stop PowerShell logic moved to scripts/smoke.ps1 and scripts/stop-dev.ps1
```

Checked:

```text
uv sync --locked --extra dev: passed
uv run pytest: passed
uv run ruff check: passed
uv run ruff format --check: passed
local uvicorn smoke: /api/health/live, /api/health/ready, /api/warmup passed
docker build -t alextym-backend-uv .: passed
task --list: passed
task backend:check: passed
task ci: passed
task --dry dev/stop/smoke: passed
task stop with unused ports: passed
task smoke syntax: passed, failed correctly when backend was not running on port 8000
task ci after Taskfile smoke/stop fix: passed
frontend npm run lint: passed
frontend npm run build: passed
```

Post-Stage 1 maintenance:

```text
frontend GitHub CI job now runs npm run lint before npm run build.
frontend/.eslintrc.json added so next lint runs non-interactively.
npm install reports 5 dependency audit vulnerabilities: 1 moderate, 4 high.
Do not fix dependency upgrades without a separate decision, because npm audit fix --force may introduce breaking changes.
```

Done in Stage 2:

```text
visual frontend shell based on the provided screenshots
top pill menu with Home, Resume, Chat and theme toggle
home page card grid
separate /chat UI placeholder with quick prompts, reset, warm-up status and mock response
/resume page with public CV download link placeholder
/contact page UI placeholder with LinkedIn, GitHub and Facebook links
local frontend /api/* rewrite support through BACKEND_ORIGIN in next.config.mjs and Taskfile.yml
```

Checked in Stage 2:

```text
npm run lint: passed
npm run build: passed
local frontend /api/warmup via BACKEND_ORIGIN rewrite: passed
headless visual screenshots checked for /, /chat desktop, /chat mobile, /resume and /contact
Browser plugin local navigation attempted but blocked by ERR_BLOCKED_BY_CLIENT; headless Chrome was used as fallback.
```

Done in Stage 3:

```text
backend chat schemas for request, response and source metadata
POST /api/chat JSON fallback endpoint
POST /api/chat/stream SSE endpoint
thin FastAPI chat router
ChatService orchestration placeholder
deterministic insufficient-data response
basic prompt injection guard for instruction/system prompt extraction attempts
safe SSE error event for unexpected stream failures
```

Checked in Stage 3:

```text
pytest via bundled Python + backend .venv site-packages: passed
ruff check via backend .venv: passed
ruff format --check via backend .venv: passed
```

Deferred after Stage 3:

```text
rate limiting
```

Done in Stage 4A:

```text
public knowledge boundary: backend/knowledge/resume.md only
private draft boundary through ignored private/knowledge/
backend/knowledge/biography_public.md and backend/knowledge/projects.md ignored at this stage
heading-aware markdown chunker
chunk metadata model
in-memory retriever abstraction for local tests
prompt builder with separated system instructions, retrieved context and user question
ChatService wired to retrieval abstraction without external OpenAI/Qdrant calls
RAG tests for chunking, metadata, retrieval, prompt building and knowledge loading
```

Done in Stage 4B:

```text
OpenAI dependency and provider clients for embeddings and Responses API
Qdrant dependency, vector store and retriever
idempotent public knowledge ingestion script
task rag:ingest command
ChatService integration with LLM answer generation and safe extractive fallback
provider tests with fake OpenAI/Qdrant clients
```

Done in Stage 4C:

```text
frontend chat shell connected to POST /api/chat/stream
incremental SSE token rendering
source metadata display
JSON /api/chat fallback when streaming is unavailable
reset/abort handling for in-flight chat requests
chat error and fallback notices
```

Done in RAG activation:

```text
backend local .env loading for app settings and ingestion
Taskfile backend commands moved to ignored .tmp uv environments to avoid stale backend/.venv issues
Qdrant source payload keyword index for idempotent source cleanup
real Qdrant ingestion from backend/knowledge/resume.md
RAG score threshold default adjusted to 0.5 after real retrieval score checks
OpenAI reasoning effort default set to low for stable short Responses API answers
link/reference sections filtered from normal professional retrieval unless the user asks for links
quick prompts updated to retrieval-friendly employer-facing questions
```

Checked in RAG activation:

```text
OpenAI embeddings request: passed
Qdrant collection setup and source cleanup: passed
task-equivalent ingestion: indexed 20 chunk(s) from resume.md
task rag:ingest: passed with isolated uv ingestion
real ChatService checks: professional summary, FastAPI/backend, AI-assisted/RAG, GitHub link, health-data refusal and prompt-injection refusal passed
```

Done in RAG answer quality pass:

```text
frontend chat answers render paragraphs and bullet lists instead of collapsed plain text
RAG score threshold default adjusted to 0.4 after short SQL question checks
lightweight query expansion added for SQL/database, FastAPI/backend, RAG/AI, projects and common employer wording
public resume knowledge now states practical SQL/database experience explicitly
```

Done in Stage 5 backend contact and rate-limit hardening:

```text
process-local daily rate limiting for /api/chat, /api/chat/stream and /api/contact
/api/chat and /api/chat/stream limit: 50 messages per IP per day
/api/contact limit: 5 messages per IP per day
POST /api/contact with validation, honeypot handling and safe generic errors
Resend email provider behind backend-only RESEND_API_KEY, CONTACT_TARGET_EMAIL and CONTACT_FROM_EMAIL
```

Done in Stage 5B frontend contact integration:

```text
/contact form posts to /api/contact
frontend handles sending, success, validation, rate-limit and delivery-error states
hidden company_website honeypot is submitted without exposing private contact details
```

Done in hybrid chat behaviour pass:

```text
greetings and help requests respond naturally without RAG
general non-Alex questions can be answered like a normal AI chat
factual questions about Alex still use RAG and source metadata
private personal data requests are refused before retrieval
short conversation history supports English follow-up questions such as "Tell me about him"
third-party people such as Elon Musk return a scope-boundary response instead of Alex RAG
```

Next step:

```text
Run a pre-deployment readiness and privacy audit, then prepare Stage 6 deployment.
Do not start without explicit instruction from the user.
```

---
## Roadmap

### Stage 1 — Project skeleton

- [x] Frontend skeleton.
- [x] Backend skeleton.
- [x] Dockerfile.
- [x] Health endpoints.
- [x] Warmup endpoint.
- [x] `vercel.json`.
- [x] Basic tests.

### Stage 2 — Chat UI

- [x] Home page.
- [x] Chat page.
- [x] Quick prompts.
- [x] Warm-up request.
- [x] Loading/error states.
- [x] Mock response placeholder.
- [x] Production streaming UI.

### Stage 3 — Backend chat service

- [x] Thin router.
- [x] ChatService.
- [x] JSON fallback.
- [x] SSE endpoint.
- [x] Insufficient-data response.
- [x] Basic prompt injection guard.

### Stage 4 — RAG

- [x] Public knowledge boundary.
- [x] Chunker.
- [x] Metadata.
- [x] Embeddings.
- [x] Qdrant ingestion.
- [x] Retriever abstraction.
- [x] Prompt builder.
- [x] Real Qdrant/OpenAI activation check.

### Stage 5 — Resume and Contact

- [ ] Resume page.
- [ ] CV download.
- [x] Contact form backend.
- [x] Contact form frontend.
- [x] Honeypot.
- [x] Resend integration.

### Pre-public security hardening

- [x] Chat rate limiting up to 50 messages per IP per day.
- [x] Contact form rate limiting.
- [x] Contact form honeypot.
- [ ] LLM provider budget limit.

### Stage 6 — Deployment

- [ ] Vercel frontend.
- [ ] Koyeb backend.
- [ ] Qdrant Cloud.
- [ ] Cloudflare DNS.
- [ ] UptimeRobot keep-alive.
- [ ] Production smoke test.

---

## Security & Privacy

Mandatory rules:

- do not commit `.env`;
- do not commit `_local`;
- do not commit `private/`;
- do not publish the private biography;
- do not add to GitHub and/or the project health information, personal contacts, names of colleagues, friends, managers, or any other private or personalised data;
- do not store secrets in the frontend;
- do not log the full system prompt;
- do not log private data unless necessary;
- add rate limiting;
- chat limit is 50 messages per IP per day;
- contact limit is 5 messages per IP per day;
- contact form honeypot is implemented;
- set an LLM budget limit;
- use only reviewed public knowledge files for RAG.

---

## How to update this file

After each major change, add a short entry:

```text
Date:
Done:
Checked:
Problems:
Next step:
```

After each change, update the relevant documentation sections.

After each change, the following files must be updated accordingly: README.md, AGENTS.md, SESSION_NOTES.md

If the file becomes long again — move details to `docs/`.
