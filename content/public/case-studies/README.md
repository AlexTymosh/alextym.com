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
