# SESSION_NOTES

## Scope

Branch: `feat/case-study-rag-pipeline`

Goal: add structured public case studies to the existing resume-based RAG pipeline without
creating a parallel knowledge architecture or weakening source validation.

Current branch state reviewed on 2026-08-02:

- The branch is based on `main` and contains ten `**/*.case.md` source files.
- `README.md` and `CASE_STUDY_TEMPLATE.md` are documentation-only files.
- `backend/app/rag/case_study_contract.py` owns production source parsing and validation.
- Repository and negative tests import the shared production contract.
- No semantic chunk generator, generated case-study artifact, or Qdrant ingestion exists yet.
- Existing production RAG ingestion is still resume-specific.

## Architectural decisions

1. `resume.md` and case studies remain separate canonical source types.
2. Only `**/*.case.md` is eligible for case-study parsing and indexing.
3. A front-matter `id` is the canonical stable identifier; file names may remain concise.
4. `parentEntryId` links a case to a relevant resume entry, including experience,
   education, or project entries.
5. `section` must match the linked parent entry section.
6. Each case stores one `date` value in `YYYY` or `YYYY-MM` format.
7. When a previous source had a date range, `date` uses the end or completion date.
8. The case date must fall within the known parent entry period.
9. Public availability and exclusion from website rendering are properties of this source
   directory, not repeated front-matter fields.
10. Retrieval hints and tags are retrieval metadata, not answer content.
11. Source parsing uses a shared contract module rather than duplicating validation between
    tests and production code.
12. Case studies will use the existing Qdrant collection and a unified generated knowledge
    dataset.

## Delivery plan

### Stage 1 — Correct sources and define schema

Status: **completed in branch**

Completed changes:

- Renamed `parentExperienceId` to the semantically correct `parentEntryId` in all ten cases,
  the template, documentation, and structural tests.
- Simplified front matter by removing metadata that is identical for every case or unrelated
  to case-study ingestion.
- Replaced `startDate` and `endDate` with a single required `date` field.
- Used the end or completion date where a previous date range existed.
- Corrected the corporate credit-risk case from `section: experience` to
  `section: education` so it matches its parent resume entry.
- Corrected the procurement case date to `2026-04` so it does not extend beyond the linked
  employment period.
- Refined the IoT result wording so the software defect is stated as resolved while the
  hardware-layout or interference finding remains explicitly probable and evidence-backed.
- Normalised `the Owner` inside sentences while retaining `The Owner` at sentence starts.
- Updated the template to include the required `case-study` primary tag.
- Expanded the case-study README with field semantics, the single-date rule, and parent rules.
- Strengthened the existing repository test to verify:
  - the exact ten expected case IDs;
  - the simplified metadata schema;
  - absence of removed metadata fields;
  - parent entry existence;
  - parent/case section consistency;
  - case-date containment within known parent dates;
  - template/schema alignment;
  - responsible Owner wording.

Impact analysis:

- Changes affect only case-study content, case-study documentation, and its structural test.
- `resume.md` is unchanged.
- No production parser currently consumes these fields, so the schema correction does not
  create a runtime compatibility regression.
- No new issue is required for Stage 1.

### Stage 2 — Centralise the source contract

Status: **completed in branch**

Completed changes:

- Added `backend/app/rag/case_study_contract.py` as the production source of truth.
- Added strict Pydantic v2 metadata models with aliases matching canonical front matter and
  `extra="forbid"` for unknown fields.
- Added `yaml.safe_load` parsing with domain-level `CaseStudyContractError` messages.
- Added deterministic `**/*.case.md` discovery that excludes documentation files.
- Added fenced-code-aware H1/H2/H3 parsing without introducing a general-purpose Markdown
  dependency for the intentionally narrow source format.
- Added semantic section models, normalized section slugs, and multiline retrieval-bullet
  preservation.
- Added resume parent-entry parsing and collection-level validation for duplicate IDs,
  parent existence, section consistency, date overlap, and the expected source set.
- Declared PyYAML as a direct runtime dependency because production code imports it.
- Reduced `backend/tests/test_case_study_structure.py` to repository integration checks that
  call the shared production contract.

Impact analysis:

- The new module is additive and is not yet called by live chat, embeddings, Qdrant, or the
  existing resume ingestion path.
- Existing case-study source files and `resume.md` are unchanged.
- The only runtime dependency change makes an existing transitive PyYAML installation
  explicit; no additional package is introduced into the resolved environment.
- Stage 4 can consume `CaseStudyDocument` directly without duplicating source parsing.
- No new issue is required for Stage 2.

Completion criteria:

- production parsing and tests use one contract;
- production code contains no pytest assertions or test-only exceptions;
- repository case studies validate through the shared contract;
- multiline retrieval bullets are preserved.

### Stage 3 — Add negative contract tests

Status: **completed in branch**

Completed coverage:

- missing, unclosed, malformed, or non-mapping front matter;
- unknown metadata fields, invalid IDs, invalid dates, and empty required values;
- missing or mismatched H1 titles;
- missing, empty, misplaced, or duplicate-normalized H2 sections;
- `Retrieval` ordering and exact H3 structure;
- missing `case-study`, invalid tags, duplicate tags, and cross-group overlap;
- H3 headings outside `Retrieval`;
- unresolved template placeholders;
- headings inside fenced code blocks;
- multiline retrieval-bullet preservation;
- deterministic source discovery;
- duplicate resume and case-study IDs;
- missing parents, parent-section mismatch, and case dates outside parent periods;
- expected collection ID mismatch.

Validation:

- `task format`
- `uv lock`
- `uv run python -m pytest tests/test_case_study_contract.py tests/test_case_study_structure.py`
- `task backend:check`
- `task rag:check`
- `task ci`

No new issue is required for Stage 3.

### Stage 4 — Parse case studies into semantic chunks

Status: pending

Create:

- `backend/app/rag/case_study_rag_source.py`
- `backend/tests/test_case_study_rag_source.py`

Rules:

- one answer chunk per semantic H2 section;
- no answer chunk for `Retrieval`;
- stable IDs such as `case:<case-id>:analysis`;
- shared parent ID `case:<case-id>`;
- preserve source path, title, organisation, date, section, tags, and retrieval priority;
- keep limitations and probability language intact;
- never split a Markdown bullet in the middle;
- remove Markdown URLs from embedding inputs while retaining source references separately.

### Stage 5 — Generate deterministic case-study artifacts

Status: pending

Create:

- `.tmp/rag/case-studies.generated.chunks.json`
- `.tmp/human-readable-preview/case-studies-rag-preview.md`
- `task rag:extract-case-studies`

Validate:

- all ten case IDs are represented;
- chunk IDs are unique and deterministic;
- repeated generation is byte-identical;
- retrieval metadata is not included as answer content;
- source paths and parent IDs are present;
- all required vector inputs are non-empty.

### Stage 6 — Unify generated public knowledge

Status: pending

Generalise resume-specific names:

- `GeneratedResumeChunkBundle` → `GeneratedKnowledgeBundle`
- `load_generated_resume_chunks` → `load_generated_knowledge_chunks`
- resume-only artifact → `public-knowledge.generated.chunks.json`

Combine:

- existing resume chunks;
- new case-study chunks.

Preserve existing resume chunk behaviour and generated schema compatibility.

### Stage 7 — Extend Qdrant payload and indexes

Status: pending

Use the existing collection.

Add case-study payload fields:

- `document_type`
- `source_group`
- `case_id`
- `case_section`
- `organization`
- `parent_id`
- `dataset_version`

Add keyword indexes only for fields used by filtering, initially:

- `document_type`
- `source_group`
- `case_id`
- `case_section`

### Stage 8 — Add safe versioned ingestion

Status: pending

Required order:

1. validate and generate the complete dataset;
2. generate all embeddings;
3. derive `dataset_version` from the generated artifact hash;
4. upsert the new dataset;
5. delete stale points from the same `source_group` only after successful upsert.

This avoids deleting the active dataset before embeddings or upload succeeds and removes
stale points created by deleted or renamed sources.

### Stage 9 — Add retrieval and answer evals

Status: pending

Extend the existing generated-RAG suites rather than creating a separate evaluator:

- `backend/evals/retrieval_eval_cases_generated_rag.json`
- `backend/evals/chat_eval_cases_generated_rag.json`

Proposed retrieval questions:

- How was WEEE reporting automated?
- Give an example where additional automation was rejected because of poor ROI.
- How were procurement and order-control errors reduced?
- Give an example of BPMN-based process analysis.
- How did telemetry analysis distinguish a software defect from a probable hardware issue?
- What limitations applied to the corporate credit-risk analysis?
- How was payment reconciliation automated?
- How were practical skills verified before international placement?

Expected checks:

- correct case ID;
- correct case section;
- source attribution;
- no cross-case or cross-organisation fact mixing;
- limitations and probability language retained.

### Stage 10 — Integrate checks and documentation

Status: pending

Update `task rag:check` to include:

- case-source contract validation;
- case-study extraction;
- generated bundle validation;
- existing retrieval checks.

Update broader RAG documentation only after generated artifacts and ingestion behaviour exist.
