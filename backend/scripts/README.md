# Scripts

## Public Knowledge Ingestion

Run from the repository root:

```powershell
task rag:ingest
```

The command reads reviewed public knowledge from `backend/knowledge/resume.md`, chunks it,
generates OpenAI embeddings and replaces the matching source vectors in Qdrant.

Private drafts under `private/knowledge/` are not indexed.
