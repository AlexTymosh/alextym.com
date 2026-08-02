# Public Case Studies

This directory contains public professional case studies extracted from the
canonical resume source.

## Parsed files

Only files matching `**/*.case.md` must be parsed and indexed.

The following files are documentation only:

- `README.md`
- `CASE_STUDY_TEMPLATE.md`

File names are concise repository paths. The front-matter `id` is the canonical,
stable identifier used for validation, generated chunk IDs, and future Qdrant
payloads. Renaming a file must not silently change its `id`.

All files in this directory are public RAG sources. Website-rendering and
visibility flags are therefore not part of the case-study schema.

## Schema contract

Every case-study source uses `schemaVersion: 1` and the following metadata:

| Field | Rule |
| --- | --- |
| `id` | Required, unique, lowercase kebab-case, prefixed with `case-`. |
| `documentType` | Required and fixed to `case-study`. |
| `section` | Required and must match the linked resume entry section. |
| `parentEntryId` | Required stable ID of the related entry in `../resume.md`. |
| `date` | Required `YYYY` or `YYYY-MM` value representing completion or the most relevant known date. |
| `title` | Required and must match the single H1 heading exactly. |
| `organization` | Required public organisation or research context. |
| `location` | Optional public location. |
| `retrievalPriority` | Required and set to `low`, `normal`, or `high`. |

When a previous source had both a start and an end date, `date` uses the end or
completion date. When only a year or approximate period is known, use the most
specific supported value without inventing precision.

When the linked resume entry has dates, the case `date` must fall within that
parent period.

## Content rules

- One case study per file.
- Preserve all source facts, limitations, retrieval hints, tags, and recognition.
- Use `the Owner` inside a sentence and `The Owner` only at the beginning of a sentence.
- Do not add assistant-behaviour instructions.
- Do not include private contacts or confidential information.
- Do not present hypotheses as proven facts.
- Keep measured results separate from estimates and broad business outcomes.
- Keep `Retrieval` as the final H2 section.
- Include `case-study` in `Primary Tags`.

## Resume relationship

Each case uses `parentEntryId` to link it to the relevant employment, education,
or project entry in `../resume.md`. The case `section` must match the parent
entry's `section`.

## Validation implementation

`backend/app/rag/case_study_contract.py` is the production source of truth for
case-study discovery, front-matter validation, Markdown section parsing, tag
validation, and parent-entry checks.

The contract uses `yaml.safe_load` for YAML front matter and strict Pydantic v2
models with unknown fields forbidden. Repository tests import the same contract
instead of maintaining a separate test-only parser.

Retrieval bullets may continue across indented lines. The parser preserves those
continuation lines so later chunk generation does not silently truncate retrieval
context.

## Semantic chunk generation

`backend/app/rag/case_study_rag_source.py` converts each validated answer H2
section into one deterministic semantic chunk. The final `Retrieval` section is
metadata only and never becomes answer content.

Chunk IDs use `case:<case-id>:<section-slug>` and share the parent ID
`case:<case-id>`. Generated chunks preserve the repository-relative source path,
case title, organisation, date, resume parent, case section, retrieval priority,
and explicit tags. Markdown links and raw URLs are removed from embedding inputs
while their targets remain available in `source.links`.

Generate the local artifacts from the repository root with:

```text
task rag:extract-case-studies
```

The command writes deterministic, LF-normalised files under `.tmp/`:

- `.tmp/rag/case-studies.generated.chunks.json`
- `.tmp/human-readable-preview/case-studies-rag-preview.md`

These files are generated review artifacts, not canonical sources, and must not
be committed. Repeated generation from unchanged sources must be byte-identical.

## Unified public-knowledge artifact

`backend/app/rag/public_knowledge_rag_source.py` combines the existing resume
chunks and case-study chunks in memory without modifying either source-specific
chunk shape. Resume chunks remain first and retain their existing IDs, content,
metadata, and vector inputs; case-study chunks follow in deterministic order.

Generate the unified review artifacts from the repository root with:

```text
task rag:extract-public-knowledge
```

The command writes:

- `.tmp/rag/public-knowledge.generated.chunks.json`
- `.tmp/human-readable-preview/public-knowledge-rag-preview.md`

The JSON keeps generated schema version `2`, records source-group counts and
canonical source files, rejects duplicate chunk IDs across source types, and
requires all vector inputs to be non-empty. The existing resume-only and
case-study-only artifacts remain available for focused debugging. Normal Qdrant
ingestion consumes the unified artifact.

## Unified Qdrant ingestion

Case-study chunks are combined with resume chunks in
`.tmp/rag/public-knowledge.generated.chunks.json`. The unified artifact is the
only input used by the normal Qdrant ingestion task:

```text
task rag:ingest:generated
```

The loader derives one SHA-256 `dataset_version` from the exact generated JSON
bytes and adds normalized `document_type` and `source_group` metadata to every
chunk. Case-study points also expose `case_id`, `case_section`, `organization`,
and `parent_id` for filtering and attribution.

Ingestion validates and embeds the complete dataset before writing to Qdrant.
It then upserts the new version and waits for completion before deleting stale
points from the same source groups. This prevents an embedding or upload
failure from deleting the active dataset. The first unified run also removes
legacy resume points only after the new dataset has been stored successfully.

Keyword payload indexes are created for `document_type`, `source_group`,
`case_id`, `case_section`, and `dataset_version`. `organization` and
`parent_id` remain unindexed until retrieval starts filtering on those fields.

## Evaluation coverage

Case-study quality is measured at two separate levels:

- `backend/evals/retrieval_eval_cases_generated_rag.json` checks that the correct
  case, semantic section, source group, organisation, and attribution metadata
  are retrieved;
- `backend/evals/chat_eval_cases_generated_rag.json` checks grounded answer
  content, source attribution, limitations, and responsible uncertainty.

The focused cases cover all ten canonical case studies. They include WEEE
automation and rejected low-ROI scope, procurement controls and BPMN analysis,
IoT software-versus-probable-hardware diagnosis, credit-risk limitations,
payment reconciliation, practical skills verification, international employment
service design, Kaizen service transformation, recruitment document automation,
and pricing-data and ERP governance.

Free validation does not call OpenAI or Qdrant:

```text
task rag:check
```

It rebuilds the unified artifact, validates the eval definitions against the
canonical case-study metadata, and runs deterministic chat contracts. Live
retrieval and answer evaluation remain explicit because they use the configured
OpenAI and Qdrant services:

```text
task rag:eval:retrieval
task rag:eval:generated
```
