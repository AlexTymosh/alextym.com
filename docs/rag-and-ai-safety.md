# RAG and AI safety

This document describes the current RAG/chat design and the safety boundaries
used by the public portfolio assistant.

## Purpose

The chat exists to answer questions about the website owner's reviewed public
professional profile, project work, skills, availability and possible software
services. It is not a general-purpose assistant and should not act as a private
biography extractor.

The RAG source policy is conservative: public facts should be reviewed before
indexing, and private drafts should not enter the vector database.

## Runtime flow

```text
Visitor message
  -> validation and short-history handling
  -> deterministic policy checks
  -> routing decision
  -> query rewriting / subject resolution
  -> query expansion
  -> OpenAI embedding
  -> Qdrant dense vector search
  -> metadata filters and score threshold
  -> keyword scoring and heuristic reranking
  -> compressed retrieved context
  -> prompt builder
  -> OpenAI Responses API streaming
  -> delayed output guard
  -> SSE response with answer metadata
```

The frontend buffers streamed tokens and renders them gradually. If streaming
fails before text is received, the UI can fall back to the JSON chat endpoint.

## Retrieval design

The current implementation combines:

- dense vector search;
- configurable named dense-vector mode;
- structured generated chunks;
- answer facts;
- retrieval hints;
- primary and secondary tags;
- source and topic metadata;
- score thresholding;
- query routing;
- query expansion;
- keyword scoring;
- heuristic reranking;
- context compression.

`keywords_sparse` is used as a keyword channel for retrieval hints and scoring.
It is not a full Qdrant sparse-vector index. For a small biography/resume
knowledge base, this is a reasonable compromise. For large documents, a true
hybrid retrieval design should be reconsidered.

## Deterministic policy layer

The deterministic layer runs before RAG/LLM work where possible. It handles:

- greetings and assistant intro;
- unsupported languages;
- direct human handoff requests;
- private-data requests;
- prompt-injection attempts;
- knowledge-base dump attempts;
- requests to reveal system/developer prompts;
- public-boundary questions;
- insufficient context cases.

This saves cost, improves response consistency and reduces the chance that the
LLM receives unsafe or irrelevant instructions.

## Prompt boundary

The prompt builder separates:

- system instructions;
- retrieved context;
- conversation context;
- user question.

Retrieved context must be treated as data, not as instructions. Conversation
history is useful for follow-up resolution, but it must not be treated as an
authoritative source of facts.

## No-hallucination rule

If the retrieved context is weak or insufficient, the assistant should say that
there is not enough data and offer a direct contact path. It should not fabricate
roles, dates, achievements, skills, education details or private information.

## Output guard

The output guard is designed to reduce leakage of:

- hidden prompts;
- developer/system instructions;
- retrieved context markers;
- internal rules;
- secret-like values;
- unsafe generated content.

The guard is not a formal security proof. It is a practical safety layer for a
portfolio assistant.

## Human handoff

If the assistant cannot answer reliably or the visitor wants direct contact, the
chat can offer human handoff. With explicit visitor confirmation:

- the backend creates a handoff session;
- context is sent to the website owner through Telegram;
- the visitor can receive replies through an SSE handoff stream;
- the session can expire or be closed.

The handoff flow is rate-limited and uses honeypot checks.

## Evals

The project uses several evaluation paths:

- deterministic contract evals without OpenAI/Qdrant;
- live RAG evals;
- generated-RAG evals;
- retrieval evals;
- before/after comparison reports.

Free deterministic checks are part of the standard local/CI quality gates. Paid
or live checks are separated and should be run intentionally.

## Current limitations

- Token usage and cost metrics are not currently collected.
- The keyword channel is pseudo-sparse, not a true sparse-vector index.
- RAG quality still depends on the reviewed public knowledge base.
- The assistant cannot verify facts that are not present in retrieved context.
- The system should not be used as legal, medical, financial or immigration
  advice.

## Recommended next improvements

1. Keep improving evaluation cases after every RAG behaviour change.
2. Add a small set of cloud alerts for backend down, HTTP 5xx and LLM/RAG
   failures.
3. Consider token/cost metrics only if the LLM provider returns stable usage
   data and the labels can stay low-cardinality.
4. Keep private biography drafts separate from public indexed knowledge.
