# SESSION_NOTES.md

| Stage | Status | Scope | Verification |
| --- | --- | --- | --- |
| 1 | Complete | Audited scattered hardcoded project settings and recorded the target configuration boundaries. | Reviewed source usage and documented the intended refactor path. |
| 2 | Complete | Normalised the public resume source around `content/public/resume.md` and removed legacy `backend/knowledge/` usage. | RAG source tests and local ingestion checks passed. |
| 3 | Complete | Added the shared non-secret project configuration contract and validation. | Config validation and backend config tests passed. |
| 4 | Complete | Moved public frontend site copy, SEO data, links, and template settings onto the shared configuration layer. | Frontend type, lint, build, and Playwright checks passed locally. |
| 5 | Complete | Moved backend assistant copy and public behaviour settings onto the shared configuration layer. | Backend lint, format, compile, and pytest checks passed locally. |
| 6 | Complete | Aligned free local CI with GitHub CI and kept paid evaluation tasks separate. | Local free check suite passed. |
| 7 | Complete | Cleaned deployment configuration so backend origin and Docker build context are explicit. | Deployment config checks and Docker build passed locally. |
| 8 | Complete | Added the local project setup wizard and GUI editor for reusable template settings. | Wizard validation checks passed locally. |
| 9 | Complete | Tightened wizard scope, removed low-value editable fields, added derived defaults, and improved review before save. | Wizard and config checks passed locally. |
| 10 | Complete | Improved wizard layout, grouping, and section previews after syncing with `main`. | Wizard checks passed locally. |
| 11 | Complete | Removed duplicate RAG resume source defaults so backend RAG resolves the single public resume source through project config. | RAG checks, backend tests, and Docker build passed locally. |
| 12 | In progress | Repack local work into clean logical commits without pushing. | Pending final verification after repack. |
