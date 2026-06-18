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
