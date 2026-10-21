# Session_Notes — Fleet VOR Hub v2

**Status:** PR-01 implementation patch prepared; local SQLite freeze and G0 verification pending  
**Prepared:** 20 October 2026  
**Project:** `AlexTymosh/alextym.com` · Next.js frontend + FastAPI backend + SQLite  
**Working language:** British English for UI, API and code; explanatory discussion may be in Russian  
**Intent:** A realistic, entirely synthetic SCAS / PTS Fleet operational demonstration, not a production integration.

---

## 0. Decisions confirmed by the user

1. Preserve the **entire current Fleet VOR Hub v1 experience** at `/fleet-vor-hub-01`, including a full, point-in-time copy of its existing SQLite data: vehicles, tickets, messages, history, contacts, subscribers, workflow progress, bookings, etc. The two applications must then behave independently.
2. Continue development on `/fleet-vor-hub`; v1 is a frozen, functioning reference and presentation alternative.
3. The **PTS Fleet** and **Fleet Department** names refer to the **same team**.
4. **OSD (Operations Support Desk)** records driver-reported breakdowns in HOTH (House on the Hill). Fleet Department presently receives HOTH notifications via ordinary Outlook email. Do **not** assume an operational HOTH/KEY2 API integration.
5. For **Standard Defect**, Fleet Department owns the repair-coordination workflow. For **Wheels / Tyres** and **Windscreens**, the **HOTH team** owns the specialist process; PTS Fleet is informed and handles applicable KEY2 status recording, but does **not** need a tyre/windscreen repair workflow.
6. **Remove COMMS and Misfuelled** from the PTS Fleet demo's selectable high-level VOR reasons and standard workflow scenarios.
7. High-level reasons under consideration: `Mechanical`, `Accident Repair`, `Warranty`, `Equipment`, `Missed Event(s)`; retain `Unknown / Under Investigation` for cases lacking a confirmed cause. Distinguish high-level reason, defect type, and detailed fault description.
8. **VOR → Available in KEY2 is a separate, manual, auditable confirmation by Fleet Department**. It must never happen automatically when a repair step, release checklist, HOTH notification, or document task is completed.
9. `Requirement = 25` means a minimum of **25 vehicles operational at any given time**, not 25 total vehicles.
10. Add a separate `/fleet-vor-hub/new-defect` page. Link to it from the workspace, but keep the registration form off the processing page. **Do not include Next Action Owner or Next Action Deadline in that registration form.** These may be assigned later in case management.
11. Use a dense asset-card style inspired by Insytly: compact layout, green and red status chips, neutral white/light grey surfaces, contextual icons, readable progress indicators. Red is explicitly allowed.
12. Teams notification via a channel email address may be offered **only if simple and proven permitted**. No Microsoft Graph/Power Automate dependency for the demo. Default: simulated notification; real delivery requires an explicit opt-in and verified test address.
13. First deliver this approved plan and freeze v1. **Do not begin implementing features before the v1 isolation and verification gate passes.**

## 1. Baseline inspected in the existing GitHub repository

- `frontend/app/fleet-vor-hub/page.tsx` renders `VorHub`.
- `frontend/app/fleet-vor-hub/VorHub.tsx` currently handles the vehicle workspace, workflow, contacts, messages, dashboard and calendar in one component; future work should split views without breaking behaviour.
- `frontend/next.config.mjs` already proxies `/api/:path*` to the backend when `BACKEND_ORIGIN` is set. New `/api/vor-01/*` routes fit that generic rewrite, subject to deployment verification.
- `backend/app/api/vor.py` currently defines `/api/vor/*`, one session cookie `vor_demo_session`, and login/logout, read, workflow, contact, email and booking endpoints.
- `backend/app/services/vor_store.py` uses `VOR_DEMO_DB_PATH` or `backend/_local/vor_hub.sqlite3`, seeds from `vor_seed.sqlite3` if missing and applies versioned migration functions. A copied v1 DB must **never** be migrated by the new v2 service by accident.
- `.gitignore` excludes `_local/`, `.env` and development artefacts. Existing, potentially sensitive or mutable SQLite files must **never** be committed to Git.
- Current XLSX export is built from a live database snapshot; this is distinct from making a full, restorable SQLite backup.
- Existing FastAPI tests use temporary SQLite paths and can be extended to test version isolation.

**Baseline qualification:** Repository inspection describes code on the default branch as inspected on 20 October 2026. Before editing, re-check the current branch/commit and local vs deployed data source; the running demo database is not present in GitHub.

## 2. Product boundaries and navigation

| Route | Purpose | State | Database |
| --- | --- | --- | --- |
| `/fleet-vor-hub-01` | **Frozen v1** reference, full historic data copy | Independent | `vor_v1.sqlite3` or environment-equivalent |
| `/fleet-vor-hub` | **Active v2** Fleet Workspace | Independent | `vor_v2.sqlite3` or environment-equivalent |
| `/fleet-vor-hub/new-defect` | Register a new defect / linked HOTH notice | v2 | v2 only |
| `/fleet-vor-hub/process` | AS-IS / TO-BE process map + RACI | v2 | Mostly static/versioned |
| `/fleet-vor-hub/actions` | Next actions, deadlines, blockers, documents | v2 | v2 only |
| `/fleet-vor-hub/reconciliation` | HOTH vs KEY2 review and imports | v2 | v2 only |
| `/fleet-vor-hub/settings` | Reason codes, configurable workflows, contacts | v2 | v2 only |
| `/fleet-vor-hub/status-history` | Auditable status changes | v2 | v2 only |
| Dashboard and Calendar | May remain tabs within v2 workspace | v2 | v2 only |

Avoid overloading the main menu: top-level workspace/dashboard/calendar; other tools may live in a **Tools / Operations** menu, with visible access to **New Defect**. Keep v1 discoverable by a discreet "Previous demo" link; do not embed the old workspace into v2 components.

## 3. Milestone 0 — Freeze and isolate v1 (BLOCKING)

**Objective:** Users can operate the existing version at `/fleet-vor-hub-01` exactly as before, while all future changes at `/fleet-vor-hub` are independent.

### Tasks

- [ ] Identify the **actual running** original SQLite database and the source environment; inspect schema, row counts, file integrity, schema migration versions and expected records without revealing secrets. Do not assume the local database equals the deployed database.
- [ ] Create an atomic, consistent snapshot of the **active** v1 DB using SQLite's **backup API** (or equivalent transactional backup). Avoid blindly copying an open WAL-mode file. Keep timestamp, source environment and checksum in a private backup manifest.
- [ ] Record baseline row counts for all user data tables: vehicles, tickets, events, ticket steps, workflow templates, contacts, subscriptions, bookings, email attempts, daily stats and any additional tables.
- [ ] Initialise two physically separate database files from the agreed snapshot: one frozen v1 copy; one starting-state copy for v2. Retain a third private backup/rollback copy until verification succeeds.
- [ ] Create a versioned, stable v1 frontend route with its own frozen TSX/CSS. No later shared stylesheet/component changes may alter v1's appearance or behaviour.
- [ ] Provide explicit version-specific backend routing and storage dependencies (e.g. `/api/vor-01/*` and `/api/vor/*`); do not rely on one global `VOR_DEMO_DB_PATH` for both.
- [ ] Separate session-cookie names and paths, and if appropriate signing context, so logging into/out of one version does not authenticate or log out the other accidentally. Preserve current password UX unless a change is explicitly required.
- [ ] Ensure **new v2 migrations apply only to v2**. Freeze a compatible v1 data access layer and schema or version it carefully to preserve old behaviour.
- [ ] Do not send duplicate real emails during snapshot creation or test operations. Disable live delivery in test suites.
- [ ] Verify all old behaviour independently: login, contacts, subscriptions, messages, existing history, emails in simulated mode, booking, workflow progression, export, calendar.
- [ ] Write bidirectional isolation tests: mutate each version's vehicle/workflow/contact/subscriber/message/booking and assert zero changes in the other version's tables and API responses. Also test two simultaneous sessions and one-sided logout.
- [ ] Document deployment persistence. If host storage is ephemeral, define an approved demo persistence/restore strategy; **never** imply a ZIP, Git commit or redeploy automatically preserves a hosted SQLite file.

**Exit gate G0:** v1 and v2 independently start from matching snapshot data; mutations and cookies remain isolated; v1 UI remains unchanged; backups verified; build and tests pass. **No v2 feature work before G0.**

## 4. Milestone 1 — v2 domain model and data foundation

Design v2 around **vehicle**, **VOR case/defect**, **task**, **workflow**, **system status** and **communication event**; never treat a vehicle's latest issue text as its entire repair history.

### Core entities / example fields (final schema subject to migration review)

| Entity | Key fields | Rules |
| --- | --- | --- |
| `vehicles` | id, registration, model, type, home_base, external references | One asset can have multiple historical cases; registration unique or controlled aliasing |
| `vor_cases` | id, vehicle_id, defect_type, reason_code, reported_at, description, source, hoth_ref, case_owner_team, state | Case lifecycle distinct from vehicle availability |
| `case_steps` | case_id, template_version_id, step_key, status, started_at, completed_at, comment | Skippable steps require explanation; preserve history |
| `workflow_templates` / versions | id, code, title, ordered_steps_json, active, version | Editing a template must not rewrite completed cases |
| `tasks` | case_id, next_action, owner, due_at, blocked_reason, completed_at | Owners/due dates set in case workflow, **not** on New Defect form |
| `vor_status_events` | vehicle_id, old_status, new_status, effective_at, recorded_at, actor, reason, source, reference | Append-only audit; **manual** release from VOR |
| `documents` | case_id, document_type, received_at, verified_at, status | Keep repair completion, documents, system update separate |
| `system_snapshots` | source HOTH/KEY2, imported_at, source_as_of, batch_id | Demo-only imports; source data retains provenance |
| `reconciliation_results` | comparison_batch_id, vehicle_id, type, outcome, owner, acknowledged_at | Difference is not automatically an error |
| `daily_capacity` | date, location/type (optional), required, operational, available, vor | Requirement defaults to 25 in overall PTS demo |
| `event_log` | case_id, vehicle_id, kind, channel, source_ref, actor, occurred_at | Visible chronological communication/activity history |

Use SQLite migrations that preserve existing v2 records. Foreign keys, indexes, checks, unique external references, UTC timestamps with UK-local display and meaningful audit events are required.

### Vehicle register and import

- [ ] Add `Vehicles` management via a separate register/import UI, not in the message composer.
- [ ] Accept **CSV and XLSX**, normalise headers and registration formats; provide mapping preview, required-field validation, deduplication, safe upsert/skip modes and error summary.
- [ ] Import never silently erases manual changes or case history; disable spreadsheet formulas as executable input, constrain size and file type.
- [ ] Permit adding vehicles manually and archiving assets. **Remove from active VOR list** closes or hides the case according to an explicit rule; never deletes vehicle/history.
- [ ] Seed enough synthetic vehicles to make Requirement=25 a meaningful dashboard baseline; 20 total assets cannot demonstrate 25 operational ones.
- [ ] Add history of status transitions, sources and corrections; historical rows remain queryable after case closure.

**Exit gate G1:** import + manual asset creation work, repeated imports are idempotent, multiple cases per vehicle persist, audit trail survives reload and export.

## 5. Milestone 2 — Process Design and registration

### AS-IS / TO-BE page

- [ ] Build a readable Lucidchart-like flow diagram (SVG/React Flow or equivalent), with swimlanes: Driver, OSD, PTS Fleet (Fleet Department), HOTH specialist team, Garage/Supplier, KEY2/HOTH systems.
- [ ] AS-IS: *"Detailed BPMN mapping can be provided on request."* State observed pain points as **proposed assessment**, not formally audited facts: unclear RACI and procedures, >1,000 emails/month reviewed in parallel, five communication channels, fragmented tracking.
- [ ] TO-BE heading disclaimer: *"A pragmatic solution within current operational constraints; further improvements are possible."*
- [ ] Driver reports issue → OSD registers HOTH ticket → roadside breakdown decision (Yes: **external process, out of scope**) → choose `Standard Defect`, `Wheels / Tyres`, or `Windscreen`.
- [ ] Standard Defect: notify PTS Fleet (currently Outlook; a future form/email feed is optional), create Fleet Hub case, Fleet manages repair cycle, KEY2 VOR management handled manually, OSD notified when HOTH closure is required.
- [ ] Wheels/Tyres and Windscreen: process owner is HOTH specialist team; **no Fleet repair workflow**; notify Fleet of VOR / return-to-service conditions, with manual Fleet KEY2 recording.
- [ ] Show ownership and notification boundaries; do not invent automated HOTH/KEY2 system writes.

### Standalone `/fleet-vor-hub/new-defect`

- [ ] Required: vehicle registration (search existing register), defect pathway, description, source/received-at, VOR indication.
- [ ] Optional/conditional: HOTH reference (if known), high-level reason, workshop/supplier, reported location, supporting narrative. Validate duplicates and choose existing open case where appropriate.
- [ ] **Do not show or require Next Action Owner or Next Action Deadline on this page.** Assign these in a later processing step.
- [ ] Saving creates a new case, initial activity record, source reference and workflow **only for Standard Defect**. Non-standard cases are monitored without Fleet workflow.
- [ ] Provide confirmation with **Open case** link, and a link back to the workspace.
- [ ] Real emails/Teams alerts are **off by default**. Implement simulated notice; optional external Teams channel email only after an administrator permits outside senders and a manual personal-email-to-channel test succeeds.

**Exit gate G2:** diagram branches are correct, form creates a linked case without duplicating vehicle, specialist routes do not create Fleet-owned repair stages, no external email is sent in demo mode.

## 6. Milestone 3 — Standard Defect workflow and operational control

### Single universal Standard Defect workflow (8 stages)

1. **Defect registered with service provider** — awaiting provider acknowledgment.
2. **Initial diagnosis scheduled** — awaiting diagnosis result.
3. **Awaiting quotation** — awaiting estimated repair cost.
4. **Repair authorisation** — approval pending / recorded.
5. **Repair in progress** — work under way.
6. **Repair completed / release checklist** — physical repair and release checks verified.
7. **HOTH closure notification** — send/request confirmation that HOTH closure has been actioned (do not automatically close HOTH).
8. **Post-repair documentation** — final paperwork and record-check follow-up.

- [ ] Templates editable through Settings, with schema versioning, ordering, conditional applicability and explicit `Not required` + reason.
- [ ] Add each case's **next action**, accountable owner, due date, wait state, blockers and escalation indicator on the processing workspace (not the registration form).
- [ ] Use a calendar picker and due-state calculations with timezone-safe handling. Badge `+N` must represent **N unresolved attention items**, not the number of all events/messages.
- [ ] Release checklist: repair confirmed, relevant safety/quality check completed, operational readiness confirmed by designated PTS representative, release timestamp/actor recorded. Other necessary checks must be configurable.
- [ ] **VOR release is explicitly separate:** an authorised Fleet operator presses `Confirm KEY2 status updated` / `Mark available (manual confirmation)`, entering timestamp, actor and optional KEY2 reference. Confirming any workflow step never changes status automatically.
- [ ] Distinguish `Repair completed`, `Documents received`, `KEY2 status updated` and `HOTH closure acknowledged`; display independent indicators even if the 8-stage overview is compact.
- [ ] Add Action & Blocker Queue and documentation checklist; use one operations page with filters rather than many tiny pages.

**Exit gate G3:** stage progression, actor/due audit, skippable steps, independent status release, overdue badges and end-of-repair checklist pass functional and regression tests.

## 7. Milestone 4 — Insytly-inspired visual system

- [ ] Maintain the new **two-column** v4 layout: compact vehicle/asset rail + broad operational workspace, not three equal columns.
- [ ] Dense rectangular asset cards, consistent rows, small indicator chips and subdued visual chrome inspired by the supplied Insytly screenshots; avoid copying branded imagery verbatim.
- [ ] Use a **green / red / light grey** status family (red explicitly approved), with amber/orange for pending if useful. Ensure readable contrast and colour-independent tooltips/text.
- [ ] Icons/badges for documents, diagnosis, awaiting response, quotation/approval, repair, overdue, unread messages and blockers. Values derive from actual v2 case/task/document state, not static JSX arrays.
- [ ] Compact 8-segment workflow strip at foot of card, with step detail on hover/click and a visible current stage.
- [ ] No large New Defect form inside the Fleet Workspace; show a navigation link to the dedicated page.
- [ ] Communication timeline remains primary; its message composer remains accessible, filters/ticket linking continue to work.
- [ ] Responsive behaviour on desktop, laptop and mobile; test long registration/model names, no clipping, horizontal overflow or unreadable stage labels.

**Exit gate G4:** screenshots reviewed at wide/laptop/mobile sizes; key operations keyboard-accessible; v1 visuals unchanged.

## 8. Milestone 5 — HOTH / KEY2 reconciliation and status history

- [ ] Standalone `Reconciliation` page with two synthetic/imported source snapshots, as-of times, match rules and review statuses.
- [ ] Classify: matching, HOTH open while KEY2 available, HOTH closed while KEY2 VOR, missing record, stale snapshot, possible exception requiring human verification.
- [ ] Flag discrepancies for operator review; **no automatic correction** to HOTH, KEY2 or official availability.
- [ ] Generate XLSX/CSV **reconciliation reports** and internal status history. A genuine **KEY2-compatible import file** is blocked until a real, documented import template is provided; do not guess column formats.
- [ ] Suggested internal status history: registration, previous/new status, effective_at, recorded_at, changed_by, source_system, reason, external_reference, acknowledgement status.
- [ ] Track closure/approval of discrepancies as events with actor/time and outcome.

**Exit gate G5:** deterministic comparisons, stale-data handling, auditable review, export correctness, source provenance and cross-version isolation tested.

## 9. Milestone 6 — Dashboard and management reporting

- [ ] `Requirement = 25 operational vehicles` as an explicit baseline with future configurable period/site/vehicle-category scope; do not mistake it for total fleet size.
- [ ] Show **Operational vs Requirement** timeline, deficit/surplus, days below requirement, fleet count, available and VOR (operational and technically available are not synonyms).
- [ ] VOR by high-level reason (`Mechanical`, `Accident Repair`, `Warranty`, `Equipment`, `Missed Event(s)`, `Unknown`) and optionally defect pathway.
- [ ] Average, median and P90 **repair duration** separately from **total VOR duration**; specify start/stop events and how unfinished cases are treated.
- [ ] Filters: date, reason, workshop/garage, supplier/partner, vehicle type. "Exclude outliers" toggles a transparently defined rule (e.g. IQR), displays retained and excluded counts and never alters stored data.
- [ ] Daily VOR Report: requirement, operational, deviation (+/-), VOR causes, actionable blockers, owners, overdue tasks, trends.
- [ ] `Predictive Fleet Availability — Coming Soon` button opens a clearly labelled *non-functional preview*, not fake model predictions. Future factors: seasonality, demand, repairs, capacity and fault history.
- [ ] Synthetic time series must be internally consistent with vehicle/case histories; no chart should claim actual NHS results.

**Exit gate G6:** KPI formulas are documented, date/range and outlier filters behave correctly, and sample report can be explained and reproduced from demo data.

## 10. Optional Microsoft Teams channel email experiment

1. In desktop/web Teams, open the **target channel** (not a personal chat) → `...` → **Get email address**.
2. Check **Advanced settings** for allowed senders/domains; channel email may be disabled by IT.
3. From a personal email account, send to the **channel address**, subject `Teams Email Integration Test`, plain body `This is a test from my personal email. No action required.`
4. Verify a **new channel post**, not necessarily a push notification. If no address or rejected external email, mark Teams delivery `Skipped — tenant restriction`; do not add Graph or Power Automate just to force it.
5. If successful and explicitly approved for demo, optionally send channel email via existing Resend sender under separate feature flag, recipient allowlist, strict quota and audit logs. Default remains **simulation**.

Microsoft references:
- https://support.microsoft.com/en-us/teams/teams-channels/send-an-email-to-a-channel-in-microsoft-teams
- https://support.microsoft.com/en-us/teams/teams-channels/manage-team-settings-and-permissions-in-microsoft-teams

## 11. Suggested small, reviewable pull requests

| PR | Scope | Must not change |
| --- | --- | --- |
| PR-01 | Snapshot/backup tooling, frozen `/fleet-vor-hub-01`, separate DB/API/cookies and isolation tests | Existing user data and outward look |
| PR-02 | v2 migrations, new case/status entities, CSV/XLSX importer, historical data | v1 schema/data |
| PR-03 | Process Design diagrams, new-defect route and form | v1 / unapproved external systems |
| PR-04 | Eight-step template engine, release checklist, manual VOR status, tasks/deadlines | automatic KEY2 status changes |
| PR-05 | Insytly-inspired asset cards/icons, two-column layout, usability and responsiveness | message, contacts and export semantics |
| PR-06 | HOTH/KEY2 synthetic reconciliation and status history | official HOTH/KEY2 systems |
| PR-07 | Reporting, requirement 25, MTTR/median/outliers and DS preview | v1 / actual NHS reports |

A separate PR for documentation updates may be inserted as needed. Merge only after tests, visual review, and independent-version smoke checks.

## 12. Technical validation and delivery checklist

### Backend

- [ ] SQLite `PRAGMA integrity_check` clean for every snapshot.
- [ ] All original v1 table row counts and representative records match approved backup.
- [ ] Idempotent v2 migrations, no v1 migrations/reseeding; tests on repeated restarts.
- [ ] Scoped IDs/foreign keys, rollback on partial operations and no phantom duplicate defects.
- [ ] Validated import files, controlled size, authorisation on every mutating endpoint.
- [ ] Separate cookie names/paths and separate DB connections for v1/v2.
- [ ] Real email disabled in tests; explicit flags, allowlist, mock HTTP delivery.
- [ ] Audit trail for new case, workflow changes, manual status updates and reconciliation resolutions.
- [ ] `ruff check`, `ruff format --check`, targeted and integration `pytest` suites.

### Frontend

- [ ] `npm run build`, lint/types as configured, Playwright interaction and responsive screenshots.
- [ ] New case form is on its own route with no owner/deadline fields.
- [ ] V1 old page is pixel/functionally stable; v2 navigation and two-column layout work.
- [ ] Empty, error, duplicate, overdue, unavailable, partial import and slow network states handled.
- [ ] Keyboard focus, accessible status icons and descriptive error messages.

### End-to-end demos

- [ ] Send Teams test email manually or record `feature unavailable`; no demo code dependency.
- [ ] Log into both versions; change a message/contact/workflow in one and check the other is unchanged.
- [ ] Import synthetic vehicles, register Standard Defect and demonstrate 8 stages.
- [ ] Register Wheels/Tyres or Windscreen and show no PTS-owned repair stages.
- [ ] Complete repair and paperwork but leave KEY2 VOR unchanged until separate manual confirmation.
- [ ] Simulate overdue action, missing document, status mismatch and dashboard below 25 operational.
- [ ] Export valid daily summary and reconciliation report; confirm no invented KEY2 import schema.
- [ ] Redeploy/restart test proves the planned persistence/restore contract or visibly declares demo reset behaviour.

## 13. Explicitly out of scope

- Real integration or write-back to HOTH, KEY2 or NHS/PTS production systems.
- Automatic VOR release in KEY2 or automatic HOTH case closure.
- Full roadside breakdown/recovery process map beyond a labelled branch.
- Fleet Department workflows for tyre or windscreen supplier operations.
- Microsoft Graph or Power Automate dependencies for Teams.
- Real patient, staff, supplier or fleet records uploaded to the public personal website.
- Claims that forecasting is genuinely trained or that KEY2 accepts an invented template.

## 14. Next session — first actions (do in this exact order)

1. Confirm code branch/commit and active application environment. Check whether the SQLite being demonstrated is **local** or **deployed**, and whether it can be backed up consistently.
2. List the actual v1 database tables, row counts, schema version and known bookmarks. Produce a private backup manifest and restore plan. Never check a live SQLite file or credentials into Git.
3. Implement **PR-01 only** (v1 snapshot + full isolation), including regression/isolation tests and the old UI freeze.
4. Demonstrate both versions independently and obtain explicit approval of **G0** before touching v2 schema, import or features.
5. Continue PR-02 → PR-07 as milestones pass. Update this `Session_Notes.md` after each session with decisions, completed tasks, blockers and next exact action.

## 15. Session log template

### Session YYYY-MM-DD — [short title]

- **Branch / commit:**
- **Starting state:**
- **Work completed:**
- **Files changed:**
- **Database migrations / backup ID:**
- **Tests run / results:**
- **Known issues:**
- **Decisions confirmed:**
- **Next action:**

---

**Current approval status:** PR-01 snapshot and isolation implementation supplied as a patch. **G0 is NOT yet approved**: the actual working SQLite is only accessible in the user's runtime and must be backed up and tested there before proceeding to PR-02.


### Session 2026-10-20 — PR-01 code implementation (pending local G0)

- **Branch / commit:** Proposed `feat/fleet-vor-hub-v2-foundation`; no commit made by the assistant.
- **Starting state:** GitHub `main` inspected: one SQLite path (`VOR_DEMO_DB_PATH`), one `/api/vor` router and `vor_demo_session` cookie, one frontend route.
- **Work completed:** Wrote `scripts/freeze_vor_v1.py` to take a consistent online SQLite snapshot with integrity checks, counts, SHA-256 and private rollback manifest. Implemented generation of frozen `/fleet-vor-hub-01` frontend and frozen `/api/vor-01` API/store/export code with independent cookie/path/database (optional separate v1 password; hard guard against identical DB paths). Live email disabled for frozen v1 by default. Added regression tests and operational runbook.
- **Files supplied:** `scripts/freeze_vor_v1.py`, `backend/tests/test_freeze_vor_v1.py`, `backend/tests/test_vor_v1_isolation.py`, `docs/PR01_VOR_FREEZE.md`, `Session_Notes.md`. The freeze script will also create independent archived modules and update `backend/app/main.py` **when run locally**.
- **Database migrations / backup ID:** Not yet executed against the actual runtime database; no live data copied or modified in this session.
- **Tests run / results:** Standalone SQLite/WAL backup test and mocked end-to-end freeze smoke test passed. All source transformation patterns confirmed against current GitHub main; actual application pytest/build and two-version smoke test must be completed locally.
- **Known issues:** Hosted SQLite cannot be retrieved via GitHub; if it is the authoritative running state, it must be backed up from the host first. On an ephemeral host, persistent v1 storage requires a separate deploy/restore plan.
- **Decisions confirmed:** Existing v1 DB copied in full; status return from VOR to Available requires a separate manual Fleet Department action (future PR).
- **Next action:** Extract PR-01 patch, run the freeze utility with the correct active SQLite path, run tests/build and demonstrate bidirectional isolation. Approve G0 only after all checks pass.

### Session 2026-10-20 — PR-02 Data Foundation

- **Scope:** additive v2 case/status model, CSV/XLSX import, manual asset register, archive/restore.
- **Isolation:** PR-01 frozen v1 files and SQLite remain unchanged.
- **Verification gate G1:** targeted pytest, frontend build and browser v1/v2 smoke test pending.
- **Next:** PR-03 Process Design and New Defect.

### Session 2026-10-20 — PR-03 Process Design and Defect Intake

- **Scope:** v2-only AS-IS/TO-BE process diagram and separate New Defect form.
- **Defect intake:** HOTH reference, vehicle, pathway, VOR reason, observations; no action owner/deadline fields.
- **Workflow:** Standard Defect gets the eight-stage template; HOTH-owned specialist cases have no PTS stages.
- **Status:** reported VOR does not alter KEY2/vehicle availability; release remains manual.
- **PR-02 compatibility:** corrected Operational status and last_service_date for real seeded SQLite.
- **Verification gate G2:** targeted pytest, frontend build, browser review and v1 isolation check pending.

### Session 2026-10-21 — Unified app shell and BPMN swimlanes

- **UI:** /fleet-vor-hub is one state-driven app with a collapsible Odoo-inspired sidebar; no navigation between Next.js pages.
- **Fleet data:** Vehicle Register, Add Vehicle and Import Vehicles are separate app sections (same working API).
- **Defects:** New Defect is a distinct internal section; no Next Action owner/deadline fields.
- **BPMN:** Visio-style horizontal swimlanes with SCAS roles and external Garage/Supplier, AS-IS/TO-BE tabs.
- **Compatibility:** existing v2 Workspace, Dashboard, Calendar, Excel export, login and backend APIs preserved.
- **Legacy paths:** /register, /new-defect, /process redirect to /fleet-vor-hub. Frozen v1 unaffected.
- **Verification:** run npm run typecheck and npm run build; manual browser checks on all eight app sections.

### Session 2026-10-21 — UX refinement and workflow checklist

- Removed visible brand/system references from v2 UI only; source data keys unchanged.
- Calendar: taller cells and type, vehicle-base/city, and booked-garage/partner filters. True booking city/partner fields remain future schema work.
- Defect reason: radio selection required and initially empty.
- Process: compact movable swimlane cards; roadmap still places full management dashboard in PR-07.
- Fleet Workspace: right-side persisted stage checklist; all stage items required before advance via new endpoint.
- Frozen v1 is untouched.
