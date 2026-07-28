# Public Case Studies

This directory contains public professional case studies extracted from the
canonical resume source.

## Parsed files

Only files matching `**/*.case.md` must be parsed and indexed.

The following files are documentation only:

- `README.md`
- `CASE_STUDY_TEMPLATE.md`

## Content rules

- One case study per file.
- Preserve all source facts, limitations, retrieval hints, tags, and recognition.
- Do not add assistant-behaviour instructions.
- Do not include private contacts or confidential information.
- Do not present hypotheses as proven facts.
- Keep measured results separate from estimates and broad business outcomes.

## Resume relationship

Each case uses `parentExperienceId` to link it to the relevant employment or
education entry in `../resume.md`.
