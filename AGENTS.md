# AGENTS.md

## Purpose

This file gives Codex stable project guidance.

Keep this file short and practical. Do not turn it into a second README or a full architecture document.

For detailed guidance, read only the relevant file from `docs/`.

---

## Project Summary

This repository contains `alextym`, a personal AI portfolio website for Alex.

The product has four public pages:

```text
/          -> home page
/resume    -> web resume + CV download
/chat      -> AI chat page
/contact   -> contact form + GitHub/LinkedIn links
```


---

## Current MVP Architecture

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

Routing:

```text
Frontend calls /api/*
Vercel rewrites /api/* -> backend host
```

Fallback routing:

```text
api.alextym.com + strict CORS
```

Use fallback only if Vercel rewrites break SSE streaming or cause timeout/proxy issues.

---

## Repository Layout

Expected structure:

```text
alextym/
├─ _local/
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
│  ├─ .python-version
│  ├─ pyproject.toml
│  └─ uv.lock
├─ docs/
├─ scripts/
├─ README.md
├─ AGENTS.md
├─ SESSION_NOTES.md
├─ Taskfile.yml
└─ .gitignore
```

---

## Documentation Routing

Do not read all documents by default. Read only the documents relevant to the task.

Before changing architecture, repo structure, or service boundaries, read:

```text
docs/architecture.md
```

Before changing deployment, Docker, Vercel, Cloudflare, Koyeb, rewrites, DNS, or environment variables, read:

```text
docs/deployment.md
```

Before changing RAG, embeddings, Qdrant, chunking, retrieval, prompts, or assistant behaviour, read:

```text
docs/rag-pipeline.md
```

Before changing endpoints, schemas, response formats, SSE, validation, or API errors, read:

```text
docs/api-contract.md
```

Before changing secrets, logging, rate limiting, contact form, prompt injection handling, or personal data handling, read:

```text
docs/security-privacy.md
```

Always read:

```text
SESSION_NOTES.md
```

before starting work, because it contains the current stage and immediate task boundaries.

---

## Work Style

Follow these rules:

1. Work in small, reviewable steps.
2. Do not implement unrelated features.
3. Do not rewrite large parts of the project unless the task explicitly requires it.
4. Prefer minimal working vertical slices.
5. Keep routers thin; put orchestration in services.
6. Add or update tests for backend logic.
7. Update documentation when architecture, deployment, API contracts, or RAG behaviour changes.
8. If something cannot be verified locally, state that explicitly in the final report.

For complex tasks, first produce a short plan, then implement.

---

## Backend Rules

Backend framework:

```text
FastAPI
```

Required endpoints:

```text
GET  /api/health/live
GET  /api/health/ready
GET  /api/warmup
POST /api/chat
POST /api/chat/stream
POST /api/contact
```

Rules:

- `/api/health/live` must be cheap and must not call external APIs.
- `/api/health/ready` may check configuration and important dependencies.
- `/api/warmup` must be implemented as a lightweight warm-up endpoint and must not perform expensive operations.
- `/api/chat/stream` is the primary chat endpoint for UI.
- `/api/chat` is the JSON fallback.
- Keep FastAPI routers thin.
- Put business orchestration in `app/services/`.
- Put RAG logic in `app/rag/`.
- Put LLM provider logic in `app/llm/`.
- Use Pydantic schemas for request and response models.
- Do not expose raw provider errors to users.

---

## Frontend Rules

Frontend framework:

```text
Next.js + TypeScript + Tailwind CSS
```

Rules:

- Keep the home page as a simple standalone page.
- Put the AI chat experience on `/chat`, not on the home page.
- Use `/api/*` from the frontend; do not call the backend host directly.
- Use `frontend/vercel.json` for rewrites.
- Support dark/light mode.
- Keep `/resume` and `/contact` simple for MVP.
- Add loading, error, and warm-up states for chat.
- Do not store backend secrets in frontend code.
- Do not place private biography data in `public/`.

---

## RAG Rules

Use RAG, not fine-tuning.

Public knowledge files:

```text
backend/knowledge/biography_public.md
backend/knowledge/resume.md
backend/knowledge/projects.md
```

Do not index or commit the full private biography.

Do not add health information, private contacts, names of colleagues, friends, managers, or other private/personalized data to GitHub, project files, public knowledge files, or frontend code.

The assistant must:

- answer as Alex's digital assistant, not as Alex directly;
- use retrieved public context;
- avoid unsupported claims;
- say when information is insufficient;
- refuse prompt extraction and instruction override attempts.

Do not invent:

- dates;
- employers;
- roles;
- projects;
- technologies;
- achievements;
- certifications;
- immigration/work status;
- personal stories;
- links.

---

## Security and Privacy Rules

Never commit:

- `.env`;
- `_local`
- API keys;
- provider tokens;
- private biography documents;
- health information, private contacts, and names of colleagues, friends, managers, or other third parties;
- private chat logs;
- generated secrets.

Required:

```text
backend/.env.example
```

Public launch must include:

- chat rate limiting up to 50 messages per IP per day;
- contact form rate limiting;
- honeypot for contact form;
- LLM budget limit;
- no secrets in frontend;
- no private biography in public repo;
- safe logging.

---

## Local Commands

Use `Taskfile.yml` from the repository root for common workflows:

```bash
task dev
task smoke
task stop
task format
task ci
```

Use `uv` for backend Python dependency management. Do not introduce legacy backend install commands.

---

## Testing Expectations

Before reporting work as complete, run the smallest relevant checks.

For backend changes, prefer:

```bash
task backend:check
```

For frontend changes, prefer:

```bash
npm run build
npm run lint
```

For Docker/deployment changes, verify at least:

```bash
docker build -t alextym .
```

If a command cannot be run in the current environment, say so clearly.

Do not claim tests passed unless they were actually run.

---

## MVP Do Not Do List

Do not add these without explicit user approval:

- Keycloak;
- user accounts;
- admin panel;
- CMS;
- blog;
- fine-tuning;
- SaaS multi-tenancy;
- paid tiers by default;
- local ChromaDB inside the backend container;
- private biography in the repo;
- UI clone of another website;
- external inspiration credits in UI/README.

---

## Definition of Done

A task is done only when:

- the requested change is implemented;
- related tests or build checks were run, or skipped with an explicit reason;
- no secrets or private biography data were added;
- relevant docs were updated if behaviour, architecture, API, deployment, or RAG changed;
- the final report lists what changed and what was verified.

---

## Current Work Boundary

Always check `SESSION_NOTES.md` for the current stage.

If `SESSION_NOTES.md` says to work on one stage only, do not proceed to later stages without explicit instruction.
