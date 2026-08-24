# Scripts

## Public Knowledge Ingestion

Run from the repository root:

```powershell
task rag:ingest
```

The command is an alias for the current structured resume pipeline:

```powershell
task rag:ingest:generated
```

The current source of truth is the public resume file referenced by
`content.publicResumePath` in `config/project.config.json`.
The pipeline extracts reviewed `## RAG` / `### RAG` sections into generated
chunks, generates OpenAI embeddings, and replaces the matching source vectors
in Qdrant.

Generated chunks are written under `.tmp/rag/` and are not a source of truth.
The old `backend/knowledge/` directory has been removed. Do not use it as a
new source location.

Private drafts under `private/knowledge/` are not indexed.

## RAG release verification

Run the complete pre-deploy RAG gate from the repository root:

```powershell
task rag:release:predeploy
```

This runs free CI plus read-only collection/retrieval verification and complete
live retrieval and answer evals. It may call OpenAI and Qdrant, but it does not
ingest or delete data.

After deploying the backend, verify both public chat transports through the
frontend rewrite and then inspect protected backend metrics:

```powershell
task rag:release:postdeploy -- --base-url https://alextym.com
task rag:release:metrics -- --base-url https://<backend-host>
```

`METRICS_TOKEN` is read from the backend environment. Reports are written only
under the ignored `.tmp/evals/` directory.
