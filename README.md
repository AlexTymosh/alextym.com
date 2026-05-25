# alextym.com

> A personal developer website with an AI chat, a RAG knowledge base, a CV and a contact form.

![Status](https://img.shields.io/badge/status-MVP%20planning-blue)
![Frontend](https://img.shields.io/badge/frontend-Next.js-black)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![RAG](https://img.shields.io/badge/RAG-Qdrant%20%2B%20LLM-purple)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## About the project

**alextym.com** is Alex's personal portfolio website with an AI chat, CV, public knowledge base and contact form.

The goal of version 1.0 is to create a business-card website with an AI chat that uses a RAG approach to answer questions about Alex's professional profile.

The AI assistant answers employers' questions about Alex's projects, skills, experience, professional path and career transition based on a public knowledge base, which includes:

- personal statement;
- work experience: roles, periods, projects, achievements and reasons for transitions;
- education;
- public projects;
- recruiter-facing biography.

In future versions, the project may be extended with dialogue escalation to Alex via Telegram, as well as the collection of questions that the assistant could not answer for subsequent manual updates to the knowledge base.

Restriction: health information, private contacts, names of colleagues, friends, managers or any other private data of third parties must not be added to GitHub, project files, the frontend or the public RAG knowledge base.

The assistant must minimise the risk of hallucinations: if there is not enough information in the retrieved context, it must state directly that it does not have sufficient data to answer.

Disclaimer:

The AI assistant is designed to answer only professional, recruiter-facing questions based on the public knowledge base.

Questions about private relationships, health, colleagues, friends, managers, private contacts or other personal matters are outside the supported scope of the project.

The public knowledge base must not contain private emails, phone numbers, addresses, names of third parties or confidential information. If the assistant generates such information, it should be treated as an unsupported AI output rather than a verified statement from Alex.

---

## Main idea

The website has a separate home page. The AI chat is located on a separate `/chat` page.

Chat page intro:

```text
Hi, I'm Alex's digital assistant.
Alex created me to help you quickly explore his background. I was built using his public biography, resume and project information.
What would you like to know?
Here are a few quick questions to start:
```

Quick questions:

```text
Give me your 30-second intro.
Tell me about your recent projects.
Tell me about your RAG work
```

The AI assistant must not present itself directly as Alex. It answers as Alex's digital assistant and uses only the public knowledge base: the CV, the cleaned recruiter-facing biography, public information about projects and, where available links exist, materials from public talks such as video recordings from Zaporizhzhia Channel 5.

Private information must not be included in GitHub, project files, the frontend or the public RAG knowledge base. This includes health information, personal contacts, names of colleagues, friends, managers and any other private data of third parties.

If there is not enough data, the assistant must state this honestly rather than inventing facts.
---

## Main pages

| Route | Purpose |
|---|---|
| `/` | Home page |
| `/resume` | Web version of the CV and CV download button |
| `/chat` | AI chat page |
| `/contact` | Contact form, GitHub and LinkedIn |

Navigation:

```text
Home
Resume
Chat
```

`/contact` remains a public page and is linked from the Connect block, but it is not shown in the top pill menu.

---

## MVP features

- AI chat.
- Quick questions for employers.
- Streaming responses via SSE.
- JSON fallback for the chat.
- RAG over public markdown documents.
- Web CV page.
- PDF CV download.
- Contact form.
- Dark/light mode.
- Responsive layout.
- Basic protection against prompt injection.
- Privacy-aware handling of biographical data.
- Readiness for deployment to Vercel + Koyeb.

---

## Architecture

```text
Browser
  -> Vercel frontend
  -> /api/* via Vercel rewrites
  -> FastAPI backend on Koyeb
  -> Qdrant Cloud for vector search
  -> LLM provider for answer generation
  -> streamed response back to browser
```

### Frontend

```text
Next.js
TypeScript
Tailwind CSS
shadcn/ui
next-themes
```

### Backend

```text
FastAPI
Pydantic
Uvicorn
HTTPX
Qdrant client
OpenAI/OpenRouter client
```

### RAG

```text
Public markdown files
  -> chunking
  -> embeddings
  -> Qdrant Cloud
  -> retrieval
  -> prompt building
  -> LLM response
```

### Deployment

```text
Frontend: Vercel Free/Hobby
Backend: Koyeb Free
Vector DB: Qdrant Cloud Free
DNS/Registrar: Cloudflare
Keep-alive: UptimeRobot or cron-job.org
```

---

## Repository structure

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
│  ├─ public/
│  │  └─ resume/
│  │     └─ alex-tymoshenko-cv.pdf
│  ├─ vercel.json
│  └─ package.json
│
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ rag/
│  │  ├─ llm/
│  │  └─ core/
│  ├─ knowledge/
│  │  ├─ biography_public.md
│  │  ├─ resume.md
│  │  └─ projects.md
│  ├─ scripts/
│  ├─ tests/
│  ├─ Dockerfile
│  ├─ .dockerignore
│  ├─ .env.example
│  ├─ .python-version
│  ├─ pyproject.toml
│  └─ uv.lock
│
├─ docs/
│  ├─ architecture.md
│  ├─ deployment.md
│  ├─ rag-pipeline.md
│  ├─ api-contract.md
│  └─ security-privacy.md
│
├─ scripts/
│  ├─ smoke.ps1
│  └─ stop-dev.ps1
│
├─ README.md
├─ AGENTS.md
├─ SESSION_NOTES.md
├─ Taskfile.yml
├─ LICENSE
└─ .gitignore
```

---

## Backend API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health/live` | Cheap check that the backend is alive |
| `GET` | `/api/health/ready` | Dependency readiness check |
| `GET` | `/api/warmup` | Lightweight backend warm-up |
| `POST` | `/api/chat` | JSON fallback for the chat |
| `POST` | `/api/chat/stream` | Streaming chat via SSE |
| `POST` | `/api/contact` | Contact form |

---

## RAG knowledge base

Only public, verified markdown files are used for RAG:

```text
backend/knowledge/biography_public.md
backend/knowledge/resume.md
backend/knowledge/projects.md
```

In the future, project material fragments cleaned of personal data may be added, as well as information extracted from public video recordings of talks on Zaporizhzhia Channel 5, if such materials are available.

The public knowledge base must not include:

- private family details;
- medical information;
- health information;
- personal contacts;
- names of colleagues, friends, managers and other third parties;
- sensitive legal details;
- personal data of third parties;
- unverified achievements as facts;
- private notes;
- secrets and keys.

The assistant's main rule:

```text
If there is not enough data in the retrieved context, do not invent an answer.
```

---

## Local launch

The recommended way to work is via Taskfile:

```powershell
task dev
```

Check the local dev servers:

```powershell
task smoke
```

Stop the local dev servers on ports `8000` and `3000`:

```powershell
task stop
```

### 1. Backend

Synchronise backend dependencies via `uv`:

```powershell
cd backend
uv sync --extra dev
```

Start the backend:

```powershell
uv run uvicorn app.main:app --reload
```

Health endpoints:

```text
GET /api/health/live
GET /api/health/ready
GET /api/warmup
```

Checks:

```powershell
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

---

### 2. Frontend

The frontend skeleton uses Next.js App Router.

```powershell
cd frontend
npm install
npm run dev
```

---

## Environment variables

The backend uses `.env`.

Example file:

```text
backend/.env.example
```

Main variables:

```text
APP_NAME="alextym API"
ENVIRONMENT="local"
FRONTEND_ORIGIN="http://localhost:3000"

OPENAI_API_KEY=""
OPENAI_MODEL=""
OPENAI_EMBEDDING_MODEL=""

QDRANT_URL=""
QDRANT_API_KEY=""
QDRANT_COLLECTION="alex_public_knowledge"

RESEND_API_KEY=""
CONTACT_TARGET_EMAIL=""

RATE_LIMITING_ENABLED="true"
CHAT_DAILY_LIMIT_PER_IP="50"
```

---

## Docker

The backend must be ready to run via Docker.

Purpose of the Docker image:

- quick start;
- portability between Koyeb, Railway, Render and Fly.io;
- no binding to a specific hosting provider;
- no local vector storage inside the container.

---

## Deployment

### Frontend

Platform:

```text
Vercel
```

Specifics:

- root directory: `frontend/`;
- custom domain: `alextym.com`;
- API requests go through `/api/*`;
- rewrites proxy requests to the backend.

Example `frontend/vercel.json`:

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

### Backend

Initial option:

```text
Koyeb Free
```

If the free backend proves unstable:

```text
Railway / Render / Fly.io
```

### DNS

Registrar and DNS:

```text
Cloudflare
```

Rule:

```text
Vercel DNS records must be DNS Only / grey cloud.
Do not proxy Vercel records through Cloudflare orange cloud.
```

---

## Protection against cold start

Koyeb Free may sleep when there is no traffic.

Mitigations:

- UptimeRobot or cron-job.org pings `/api/health/live`;
- the frontend makes a mandatory warm-up request to `/api/warmup` when the chat is opened;
- the Docker image must be lightweight;
- the vector DB must be external;
- if there are problems, the backend can be moved to Railway/Render/Fly.io.

---

## Testing

Before a push or pull request:

```bash
task ci
```

Backend code auto-formatting:

```bash
task format
```

Backend:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Frontend:

```bash
cd frontend
npm run build
npm run lint
```

Docker:

```bash
cd backend
docker build -t alextym .
```

If a command cannot be executed in the current environment, this must be explicitly stated in the report.

---

## Documentation

Detailed documents:

| File | Purpose |
|---|---|
| `docs/architecture.md` | Architecture and MVP boundaries |
| `docs/deployment.md` | Deployment, DNS, Vercel, Koyeb |
| `docs/rag-pipeline.md` | RAG, chunking, Qdrant, prompts |
| `docs/api-contract.md` | Endpoints, schemas, SSE |
| `docs/security-privacy.md` | Security, privacy, prompt injection |

For Codex:

```text
AGENTS.md
SESSION_NOTES.md
```

---

## Licence

```text
The project code is distributed under the MIT Licence. Personal data, biographical materials and recruiter-facing content are not part of the code licence and may not be used separately without permission.
```

If third-party open-source code is added to the project, its licence must be preserved and complied with.

---

## Status

The project is at the backend chat service stage.

Completed in Stage 1:

```text
backend FastAPI skeleton
health/live, health/ready, warmup endpoints
frontend Next.js skeleton with 4 routes
frontend/vercel.json rewrite placeholder
backend Dockerfile and .dockerignore
basic health endpoint tests
```

Completed in Stage 2:

```text
visual frontend shell based on the provided screenshots
top pill menu with Home, Resume, Chat and theme toggle
home page card grid
chat page UI placeholder with quick prompts, reset, warm-up status and mock response
resume page with public CV download link placeholder
contact page UI placeholder with LinkedIn, GitHub and Facebook links
local dev /api/* rewrite support through BACKEND_ORIGIN
```

Completed in Stage 3:

```text
backend chat request/response schemas
POST /api/chat JSON fallback endpoint
POST /api/chat/stream SSE endpoint
thin FastAPI chat router
ChatService placeholder with insufficient-data response
basic prompt injection guard
backend tests for validation, insufficient data, prompt injection and SSE format
```

Not implemented yet:

```text
OpenAI integration
Qdrant/RAG retrieval
production frontend streaming integration
rate limiting
```

Rate limiting is still required before public launch:

```text
/api/chat and /api/chat/stream: up to 50 messages per IP per day
/api/contact: 3-5 messages per IP per day
```
