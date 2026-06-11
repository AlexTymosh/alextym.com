# RAG eval tasks and auto comparison

## Tasks

| Task | Cost | Purpose |
|---|---:|---|
| `rag:eval:free` | Free | Contract eval cycle without OpenAI/Qdrant |
| `rag:eval:paid` | Paid | Live RAG eval cycle with OpenAI/Qdrant |
| `rag:eval:compare` | Free | Manual comparison for two custom reports |

## Auto-cycle algorithm

Each eval task uses three files.

For paid/live RAG evals:

```text
.tmp/evals/rag-before.json
.tmp/evals/rag-after.json
.tmp/evals/rag-comparison.md
```

For free/contract evals:

```text
.tmp/evals/contract-before.json
.tmp/evals/contract-after.json
.tmp/evals/contract-comparison.md
```

When the task starts:

1. If `*-after.json` does not exist, it runs evals and writes the first
   baseline into `*-after.json`.
2. If `*-after.json` exists, the task copies it into `*-before.json`.
3. Then it clears `*-after.json`.
4. Then it runs evals and writes new results into `*-after.json`.
5. Then it generates `*-comparison.md`.

This means that after the first baseline, every next run automatically compares
the previous run with the current run.

## Run free eval cycle

```powershell
task rag:eval:free
```

First run creates:

```text
.tmp/evals/contract-after.json
```

Second and later runs create/update:

```text
.tmp/evals/contract-before.json
.tmp/evals/contract-after.json
.tmp/evals/contract-comparison.md
```

## Run paid/live eval cycle

This may call OpenAI and Qdrant.

```powershell
task rag:eval:paid
```

First run creates:

```text
.tmp/evals/rag-after.json
```

Second and later runs create/update:

```text
.tmp/evals/rag-before.json
.tmp/evals/rag-after.json
.tmp/evals/rag-comparison.md
```

## Recommended workflow

Before changing RAG content, run:

```powershell
task rag:eval:paid
```

Then change biography/source/chunking/prompt.

If Qdrant content changed, rebuild embeddings:

```powershell
task rag:ingest
```

This uses the generated structured resume ingestion path from
`content/public/resume.md`.

Then run again:

```powershell
task rag:eval:paid
```

Open:

```text
.tmp/evals/rag-comparison.md
```

## Manual comparison

Use this only when you want custom report names.

```powershell
task rag:eval:compare BEFORE=../.tmp/evals/rag-before.json AFTER=../.tmp/evals/rag-after.json OUTPUT=../.tmp/evals/rag-comparison.md
```

## Why Markdown comparison

A raw JSON diff answers: "Which characters changed?"

The Markdown comparison answers: "Did the chat get better or worse?"

It groups cases by:

- fixed;
- regressed;
- still passing;
- still failing;
- added;
- removed.
