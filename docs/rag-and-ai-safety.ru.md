# RAG и AI safety

Этот документ описывает текущий RAG/chat design и safety boundaries публичного
portfolio assistant.

## Назначение

Чат нужен, чтобы отвечать на вопросы о проверенном публичном профессиональном
профиле владельца сайта, проектах, skills, availability и возможных software
services. Это не general-purpose assistant и не инструмент для извлечения
частной биографии.

RAG source policy должна быть консервативной: публичные факты нужно проверять
перед indexing, а private drafts не должны попадать в vector database.

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

Frontend буферизирует streamed tokens и постепенно выводит их. Если streaming
падает до получения текста, UI может использовать JSON chat endpoint.

## Retrieval design

Текущая реализация объединяет:

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

`keywords_sparse` используется как keyword channel для retrieval hints и scoring.
Это не полноценный Qdrant sparse-vector index. Для небольшой biography/resume
knowledge base это разумный компромисс. Для больших документов нужно заново
оценить полноценный hybrid retrieval design.

## Deterministic policy layer

Deterministic layer по возможности работает до RAG/LLM. Он обрабатывает:

- greetings и assistant intro;
- unsupported languages;
- direct human handoff requests;
- private-data requests;
- prompt-injection attempts;
- knowledge-base dump attempts;
- запросы на раскрытие system/developer prompts;
- public-boundary questions;
- insufficient context cases.

Это экономит cost, повышает стабильность ответов и снижает шанс, что LLM
получит unsafe или нерелевантные инструкции.

## Prompt boundary

Prompt builder разделяет:

- system instructions;
- retrieved context;
- conversation context;
- user question.

Retrieved context должен восприниматься как data, а не как instructions.
Conversation history полезна для follow-up resolution, но не является
authoritative source of facts.

## No-hallucination rule

Если retrieved context слабый или недостаточный, assistant должен сказать, что
данных недостаточно, и предложить direct contact path. Он не должен выдумывать
roles, dates, achievements, skills, education details или private information.

## Output guard

Output guard снижает риск leakage:

- hidden prompts;
- developer/system instructions;
- retrieved context markers;
- internal rules;
- secret-like values;
- unsafe generated content.

Guard не является формальным security proof. Это практичный safety layer для
portfolio assistant.

## Human handoff

Если assistant не может ответить надёжно или visitor хочет direct contact, чат
может предложить human handoff. После explicit confirmation:

- backend создаёт handoff session;
- context отправляется владельцу сайта через Telegram;
- visitor получает replies через SSE handoff stream;
- session может истечь или быть закрыта.

Handoff flow защищён rate limit и honeypot checks.

## Evals

В проекте есть несколько evaluation paths:

- deterministic contract evals без OpenAI/Qdrant;
- live RAG evals;
- generated-RAG evals;
- retrieval evals;
- before/after comparison reports.

Free deterministic checks входят в стандартные local/CI quality gates. Paid или
live checks вынесены отдельно и запускаются намеренно.

## Current limitations

- Token usage и cost metrics сейчас не собираются.
- Keyword channel является pseudo-sparse, а не true sparse-vector index.
- RAG quality всё ещё зависит от reviewed public knowledge base.
- Assistant не может проверить факты, которых нет в retrieved context.
- Система не должна использоваться как legal, medical, financial или
  immigration advice.

## Recommended next improvements

1. Улучшать evaluation cases после каждого RAG behaviour change.
2. Добавить небольшой набор cloud alerts: backend down, HTTP 5xx и LLM/RAG
   failures.
3. Рассмотреть token/cost metrics только если LLM provider стабильно возвращает
   usage data и labels останутся low-cardinality.
4. Держать private biography drafts отдельно от public indexed knowledge.
