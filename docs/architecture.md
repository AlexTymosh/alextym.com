# Architecture

## Purpose

This project is `alextym`, a personal AI portfolio website for Alex.

The website should demonstrate:

- a modern frontend;
- a FastAPI backend;
- a RAG-based AI assistant;
- streaming chat UX;
- privacy-aware handling of personal biography data;
- deployable architecture.

The site is not just a static portfolio. The main product feature is an AI assistant that answers employer-facing questions about Alex's professional background, projects, skills, and experience.

---

## Product Scope

Required pages:

```text
/          -> home page
/resume    -> web resume + CV download
/chat      -> AI chat
/contact   -> contact form + GitHub/LinkedIn links
```

Navigation:

```text
Home
Resume
Chat
```

`/contact` remains a public page and is linked from the Connect block, but it is not shown in the top pill menu.

The home page must be a simple standalone page. The AI chat must live on the separate `/chat` page.

---

## Chat Page Intro

Use this intro text:

```text
Hi, I'm Alex's digital assistant.
This AI is augmented by my work and experiences.
Ask me about my RAG projects or AI automation workflows.
```

Quick prompts:

```text
Give me your 30-second intro.
Tell me about your recent projects.
Tell me about your RAG work
```

---

## Technology Stack

### Frontend

```text
Next.js
TypeScript
Tailwind CSS
shadcn/ui
next-themes
Framer Motion only if needed
```

Hosting:

```text
Vercel Free/Hobby
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

Initial hosting:

```text
Koyeb Free
```

Fallback hosting:

```text
Railway
Render
Fly.io
```

### Vector Database

Initial choice:

```text
Qdrant Cloud Free
```

Do not store vectors inside the backend container.

---

## High-Level Architecture

```text
Browser
  -> Vercel frontend
  -> /api/* via Vercel rewrites
  -> FastAPI backend on Koyeb
  -> Qdrant Cloud for retrieval
  -> LLM provider for response generation
  -> streamed response back to browser
```

---

## Backend Layering

Keep FastAPI routers thin.

Recommended backend structure:

```text
backend/app/api/
backend/app/schemas/
backend/app/services/
backend/app/rag/
backend/app/llm/
backend/app/core/
```

Responsibilities:

```text
api/       -> route definitions only
schemas/   -> Pydantic request/response models
services/  -> application orchestration
rag/       -> chunking, retrieval, prompt building, guardrails
llm/       -> LLM provider client
core/      -> config, logging, shared infrastructure
```

Chat flow:

```text
router
  -> ChatService
  -> Retriever
  -> PromptBuilder
  -> LLMClient
  -> structured response or SSE stream
```

---

## RAG Instead of Fine-Tuning

Use RAG, not fine-tuning.

Reasoning:

- the knowledge base is small and personal;
- updates should be easy;
- the assistant must stay grounded in source documents;
- fine-tuning is unnecessary for MVP;
- RAG is easier to explain as a portfolio project.

---

## MVP Non-Goals

Do not add these in MVP:

- user accounts;
- authentication;
- admin panel;
- CMS;
- blog;
- Keycloak;
- SaaS-style multi-tenancy;
- fine-tuning;
- paid tiers unless needed;
- local ChromaDB inside the backend container.

---

## MVP Definition of Done

MVP is ready when:

- `/` shows the home page;
- `/chat` shows the AI chat;
- `/resume` shows resume content and CV download;
- `/contact` shows a contact form;
- FastAPI backend is deployed;
- chat endpoint works;
- streaming endpoint works or has JSON fallback;
- Qdrant is used as external vector DB;
- private biography is not committed;
- the assistant does not invent facts when context is insufficient;
- deployment docs are accurate enough to reproduce setup.
