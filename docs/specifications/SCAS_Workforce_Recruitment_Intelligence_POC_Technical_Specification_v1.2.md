# Technical Specification
## SCAS Workforce & Recruitment Intelligence Portal — Proof of Concept

**Document version:** 1.2  
**Date:** 14 November 2026  
**Status:** Approved requirements baseline; implementation in progress (project grants added in Commit 02)\
**Prepared for:** Senior Data Analyst interview demonstration at South Central Ambulance Service NHS Foundation Trust (SCAS)  
**Product:** Portfolio Lab — Workforce & Recruitment Intelligence  
**Project ID:** `workforce_intelligence` (registered in the portfolio catalogue)\
**Canonical browser route:** `/portfolio/workforce-intelligence`  
**Portfolio catalogue route:** `/portfolio` (protected host route; enabled by deployment feature flag)\
**Canonical backend namespace:** `/api/workforce`  
**Primary language:** English  
**Data classification:** Synthetic demonstration data only  
**Document location in repository:** `docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md`  
**Source baseline:** Technical Specification v1.1, amended with agreed Portfolio Lab integration decisions  

### Document authority and interpretation

- **MUST / SHALL** = required for the specified release or explicitly identified phase; **SHOULD** = strongly recommended implementation; **MAY** = optional.
- **Interview MVP** means the minimum reliable end-to-end demonstration. **Full PoC** means the complete functional scope defined in this specification. The MVP does not silently replace or waive full-PoC requirements.
- The normative existing-platform baseline is the repository's `main` as reviewed after the Firebase identity merge on 14 November 2026. The implemented identity foundation must not be mistaken for completed project authorization.
- The existing Fleet VOR Hub is an architectural and visual reference, **not** a shared business-logic dependency.
- Any change to central identity, grant, session or route behavior requires integration with the authoritative Portfolio Lab specification and ADR; this project document does not independently redefine shared security architecture.

### Decision record — v1.2

| Decision | Approved requirement |
|---|---|
| Code placement | Project-owned implementation in `portfolio/workforce_intelligence/`, a sibling of `portfolio/fleet_hub/` |
| Public URL | Catalogue under `/portfolio`; protected application at `/portfolio/workforce-intelligence` |
| Interaction model | SPA-like navigation inside the existing Next.js/React website; no separate deployed SPA, router or domain |
| Visual language | Fleet-inspired component density, layouts, colors and interaction patterns, with independent scoped styling |
| Authentication | Reuse existing Firebase Authentication, using Owner-provisioned email/password accounts; OAuth providers may remain deferred |
| Authorization | One effective access level for this project: an explicitly granted project member can operate the entire synthetic demo; no Viewer/Analyst/Admin hierarchy inside this application |
| Membership source | Shared Portfolio Lab authorization control plane, not a project-owned user database or a generic identity-admission check |
| Data plane | Dedicated project-owned SQLite database with migrations, seed and audit; Render may lose/reset demo changes |
| Control plane | Existing Firebase/Firestore identity and grant state remains durable and independent from demo SQLite |
| Delivery | First ship a reliable Interview MVP, then complete the full analytical scope |
| Project isolation | No cross-project data, business-module, reset, CSS or API coupling with Fleet |

---

## 1. Executive summary

This document specifies a fully functional proof of concept for a **Workforce & Recruitment Intelligence Portal**. The product is primarily an analytical portal, not an attempt to reproduce a complete HR ERP system. It is implemented as a project module within the existing Portfolio Lab architecture, not as a standalone website.

The portal must demonstrate an end-to-end analytical process:

1. create or amend synthetic workforce and recruitment records;
2. retain the history of changes;
3. import and export structured data through Excel;
4. validate, transform and organise data into Bronze, Silver and Gold analytical layers;
5. visualise recruitment, establishment, retention, progression and employee-experience metrics;
6. generate synthetic survey responses;
7. analyse survey responses using an external AI API;
8. preserve traceability from each AI finding to the source response IDs;
9. require human review before an AI finding can be treated as a published analytical result;
10. support forecasts, scenarios and management actions.

The full portal is accessed from the shared `/portfolio` catalogue and hosted at `/portfolio/workforce-intelligence`. Internal modes and dashboard pages behave like a single-page application: navigation changes panels without unnecessary full document reloads, while remaining part of the existing Next.js application. The UI may draw inspiration from Fleet VOR Hub's navigation, surfaces, tables, filters and color system, but must not import Fleet business code or globally scoped styles.

Authentication is provided by the existing Firebase identity foundation. The Owner will provision email/password accounts and share credentials privately. Social providers are not a delivery prerequisite. Each invited user receives **one uniform Workforce demo access level** through the shared project-grant mechanism, permitting all application functions. Global Owner account/grant management remains outside this application's domain.

The dedicated Workforce SQLite database is disposable demonstration storage. A Render restart or deployment may reset synthetic records and their project-local audit history. Such a reset **must not** affect Firestore identities, grants, central policy, or central access audit records.

The visual design should resemble the navigation density and analytical character of a modern Power BI Service site, while remaining an independent product. It must not copy SCAS, NHS, Microsoft Power BI or Microsoft Copilot trademarks, logos or protected visual assets.

The application must display permanently:

> **Demo v1.0 | Prepared for an SCAS interview | Synthetic data only | Not an official SCAS system**

---

## 2. Product objectives

### 2.1 Primary objective

Demonstrate the ability of a Senior Data Analyst to design and explain a governed analytical product that connects recruitment and workforce data to evidence, forecasts and management decisions.

### 2.2 Secondary objectives

The PoC must demonstrate:

- analytical product design;
- dimensional data modelling;
- data quality management;
- metric governance;
- temporal history;
- Excel-controlled data ingestion;
- recruitment funnel analysis;
- workforce establishment and vacancy analysis;
- retention and progression analysis;
- responsible AI-assisted survey analysis;
- human-in-the-loop review;
- forecasting and scenario modelling;
- auditability and lineage;
- clear stakeholder-oriented data storytelling.

### 2.3 Non-objectives

The first version must not attempt to implement:

- payroll;
- payroll calculations;
- leave approval workflows;
- complex shift rostering;
- document management;
- automatic disciplinary or employment decisions;
- automatic promotion recommendations;
- automated wellbeing or resignation-risk scores for individuals;
- complex machine learning;
- a complete Odoo or ERP replacement;
- production safeguarding workflows;
- real SCAS employee data;
- operational ambulance performance such as 999 call volumes, response categories, Hear & Treat, hospital handover, vehicle availability or patient outcomes.

---

## 3. Scope and product boundaries

The application consists of four connected modes within **one Workforce-owned data plane**:

1. **Workforce Management:** limited administration of synthetic people, contracts, assignments, vacancies and recruitment events.
2. **Workforce Intelligence:** the primary analytical portal.
3. **People Voice:** survey creation, synthetic response generation, AI-assisted analysis and human analyst review.
4. **Data Architecture:** data layers, model, lineage, quality controls, metric catalogue and BPMN.

All four modes use one Workforce backend domain, dedicated Workforce database, authenticated session context and canonical metric definitions. They must not behave as independent mock-ups. The phrase *shared database* in this specification means shared **within Workforce**, never shared with Fleet VOR Hub or Portfolio Lab's identity/grant collections.

At least one action in each operational mode must cause a real persisted change and produce an observable impact elsewhere. Examples:

- changing contracted hours changes current WTE and the establishment-gap calculation when business conditions warrant;
- **filling** a vacancy with a valid starter affects vacancy WTE and recruitment metrics; merely closing a vacancy without filling it must **not** fabricate a reduction in the establishment gap;
- recording a candidate start updates new-starter and candidate conversion metrics;
- confirming an AI-detected survey theme publishes it into a Gold analytical view;
- rejecting an AI finding excludes it from published dashboards but retains it in project-local audit history until the next permitted demo reset.

### 3.1 Platform and domain ownership

| Owner | Responsibility | Must not own |
|---|---|---|
| Portfolio website host | `/portfolio` catalogue, route adapters, shared layout and deployment | Workforce KPIs, workflow rules, survey analysis logic |
| Shared Portfolio Lab | Firebase login, sessions, identities, project-grant decisions, central security policy | Workforce employees, vacancies, surveys, calculation rules |
| Workforce project | All four modes, domain APIs, SQLite, migrations, fixtures, analyses, metrics, project-local audit and reset | Other projects' data, central grants, Owner account administration |
| Fleet VOR Hub | Its existing vehicle demo, routes, SQLite and design implementation | Workforce data or project authorization decisions |

### 3.2 Route compatibility

- Implement `/portfolio` as the host's portfolio project catalogue, not as a redirect to a single app.
- Implement `/portfolio/workforce-intelligence` as the protected application entry route.
- Keep existing `/fleet-vor-hub` behavior and redirects unchanged. **Do not relocate Fleet** as a side effect of this project.
- Keep host Resume, Chat, RAG, Contact, Telegram, site SEO and public APIs unchanged.
- New pages must not be indexed or leaked to ungranted users. Server-side authorization protects both the UI and the backend independently.

### 3.3 SPA interaction contract

- Within the Workforce route, changing mode, report, tab, date range or service filter must not trigger a needless full-page navigation.
- Preserve shareable navigational state where feasible through URL search parameters (mode, report, period, filters), without putting secrets or free-text responses in the URL.
- Refresh/reload must restore the appropriate project screen and require a valid session/grant.
- Deep links to protected views must not bypass authorization.
- The public host manages route entry; Workforce owns feature navigation and app state.

---

## 4. Assumptions and constraints

### 4.1 Verified host baseline and pending dependencies

The existing repository uses:

- React, Next.js and TypeScript frontend on Vercel;
- Python, FastAPI and Pydantic backend on Render;
- a modular-monolith portfolio structure and project registry;
- an existing Fleet VOR Hub with its **own** SQLite data lifecycle;
- an existing externally configured AI integration;
- existing email capability (real outbound email delivery is outside this Workforce v1 scope);
- **implemented Firebase Authentication identity/session foundations**, including email/password credentials, Next.js server-side sessions, and independent FastAPI credential verification;
- Firestore-backed identity admission records and deny-all browser-client rules for control-plane data;
- a **not-yet-completed** shared project authorization, grant-administration and release workflow.

The Firebase identity foundation merged into `main` in PR #244 on 14 November 2026. At that checkpoint Portfolio Lab was disabled by default; `/lab` showed an identity preview rather than a released project catalogue. Google, GitHub and Microsoft live sign-in verification was deferred. These are statements of the reviewed implementation, **not a claim that project RBAC or the production portal is already available**.

Implementation MUST reread current `main` before editing integration points. Any subsequent platform changes supersede this baseline and should be recorded in the implementation changelog rather than assumed here.

### 4.2 Deployment characteristics

- The application is embedded in the existing website, using existing Vercel and Render services.
- The demonstration will be delivered online.
- Desktop is the primary target. Tablet and mobile layouts remain usable; detailed analytical workflows need not be mobile-first.
- Workforce SQLite is separate from Fleet SQLite. The free backend may reset Workforce data on sleep/restart/redeploy. This is **explicitly accepted** and disclosed in the UI.
- The system must support a controlled, deterministic demo reset/reseed without a separate project administrator role.
- No new paid service, hosted database or additional domain is required by default.
- Existing public-site services must continue operating if the Workforce module or its SQLite bootstrap fails.

### 4.3 Data assumptions

- Workforce scale and service categories may be based on public information.
- Individual people, outcomes, assignments, KPI values, applications, survey responses and forecasts are synthetic.
- Organisational hierarchy is a representative demonstration model, not an assertion about SCAS's internal structure.
- Publicly reported values may be shown only as sourced contextual benchmarks, never attributed to synthetic records.
- Synthetic data should have a controlled `as_of_date`, generation seed and scenario code for reproducibility.

### 4.4 Dependencies and release gates

- The **shared project membership check** must exist before any non-Owner account can access Workforce. A valid Firebase token or platform identity admission is **not** itself a Workforce project grant.
- If shared per-project authorization has not yet shipped, the MVP may be verified in an explicitly restricted Owner-only preview. This is a temporary release gate, **not** a second Workforce password system or an implicit grant to every admitted account.
- Email/password is the supported access method for this project's release. Google/Microsoft/GitHub support is optional and must not block delivery; those providers must not be advertised as enabled until live verification and platform policy allow them.
- Resettable Workforce data is independent of durable Firebase/Firestore admission and grant records.

---

## 5. Authentication, project membership and uniform access

### 5.1 One application access level

**There is exactly one effective role inside Workforce Intelligence: `Member` (authorized demo participant).** The Workforce application SHALL NOT implement Viewer, Analyst, Tester, Project Admin or Demo Owner role hierarchies, or a separate project user table for authentication.

An explicitly granted project member can:

- open every Workforce mode and published dashboard;
- inspect permitted synthetic records and drill-through details;
- add and amend synthetic people, contracts, assignments, vacancies and recruitment events;
- validate, confirm and export Excel imports;
- run surveys, synthetic response generators, forecasts and scenarios;
- initiate bounded AI analysis and use Insight Pilot;
- confirm, amend, reject and publish AI findings through an **explicit review action**;
- create and maintain management actions;
- inspect metric definitions, data quality and project-local audit events;
- reset/reseed the shared Workforce demo after an explicit confirmation step.

One role does **not** eliminate mandatory data validation, explicit publication workflow, rate limiting, safety safeguards, quotas, or audit. For example, access to publish AI results is allowed to a Member, but publication still requires an identifiable human review event.

### 5.2 Identity and project admission

- The global Portfolio Lab **Owner** provisions Firebase email/password credentials and privately sends them to visitors. The project must not send automatic credential emails.
- The platform's existing initial-password lifecycle and password-reset rules remain authoritative; this app must not implement its own password storage, hashing or expiration policy.
- The shared authorization layer must verify an explicit grant for `project_id = workforce_intelligence` and map that grant to the single Workforce `Member` capability.
- If the platform uses `No Access / View / Test / Admin` internally for other projects, Workforce must use **one selected grant/capability mapping for all Workforce participants** (a fixed project-scoped `Admin` grant, because the shared `Test` capability does not permit reset). It must not expose or interpret a new hierarchy in Workforce UI or domain code.
- Firebase UID is the stable identity subject. User-provided email, a frontend role flag, a visible UI state, an unverified token or a `project_id` supplied by the browser is insufficient authorization.
- The global Owner remains responsible for provisioning/revoking accounts and grants in the shared platform; this does **not** create a second role inside Workforce.
- Every protected page/data request is rejected when project membership is missing, revoked, expired or temporarily unverifiable.

### 5.3 Shared demo operation and concurrency

All authorized Workforce users operate on **one shared project demo dataset**, consistent with Portfolio Lab's existing project policy. They do not receive individual private databases.

- Every committed mutation must have a project-local audit event with the Firebase UID (or an opaque actor reference), timestamp and correlation ID.
- Destructive reset requires clear confirmation, must be scoped to Workforce only and must be serialized with imports/other resets.
- A successful reset increments a persistent-in-this-database `dataset_generation` or equivalent epoch and invalidates stale client caches/queries.
- Competing edits must follow documented optimistic concurrency or version-check behavior rather than silently overwrite another user.
- A reset may remove project-local audit records as part of restoring the known seed; the UI must disclose this. Durable central security audit and grants are never reset.

### 5.4 Authentication UX

- Unauthenticated visitors reaching the project are sent to the platform's existing login flow without revealing protected project data.
- Authenticated platform users without Workforce membership see a generic access-denied / unavailable state, not the project's data.
- No project-specific login form or alternative shared password is permitted.
- Sign-out invalidates the browser's current website session through the shared platform.

---

## 6. Global user interface

### 6.1 Header

The header must include:

- permanent demo disclaimer;
- four primary mode selectors;
- global date-period selector;
- global service-line selector where relevant;
- light/dark theme switch;
- authenticated account menu powered by the host session;
- data refresh timestamp and current dataset-generation marker;
- synthetic-data badge;
- clear notice when a reset/reseed has occurred.

### 6.2 Primary mode selectors

- **Workforce Management**
- **Workforce Intelligence**
- **People Voice**
- **Data Architecture**

The default landing mode must be **Workforce Intelligence**.

### 6.3 Left navigation and SPA behavior

The left navigation must remain visible on desktop and change with the selected primary mode. It may collapse on small displays. Mode switches, table filters, charts and scenario interactions use client-side React state/navigation within the project route, without full page refreshes. Preserve browser history and appropriate deep-link URL state.

### 6.4 Theme

Provide light and dark modes. Theme preference may be stored in local browser state. Charts, tooltips, grids, badges and modal panels must remain legible in both themes. Fleet-inspired visual consistency must be achieved through explicit theme tokens or neutral shared primitives, **not** imports from `fleet_hub`'s internal UI/CSS modules.

### 6.5 Brand and design treatment

- Use an original name and logo appropriate to a synthetic workforce analytics demonstration.
- Use a restrained Fleet-inspired **teal/green/neutral** palette, data-dense panels, navigation, charts, tables, drawers and action controls. Blue is optional, not mandatory.
- Preserve consistent spacing, typographic scale and interaction states with the host website where practical.
- Use scoped CSS Modules or project-owned styling; no unbounded global selectors, Fleet CSS leakage or copied SCAS/NHS branding.
- Do not use the NHS lozenge or imply an official NHS product.
- Do not copy the Microsoft Copilot icon or Power BI branding.
- The AI assistant is named **Insight Pilot**.
- Apply accessibility, keyboard navigation, contrast and responsive requirements from §24.

### 6.6 Loading, stale data and error states

- Show data loading, empty, failed, stale and suppressed states explicitly.
- A permission failure must never render previously cached protected data from another session.
- Following a reset, prevent stale SPA state from re-displaying old records; refetch the current dataset generation.
- Confirm destructive actions using contextual confirmation text and show the affected scope.

---

## 7. Synthetic data design

### 7.1 Dataset scale

Recommended initial dataset:

- approximately 4,400 synthetic employee records to represent publicly described organisational scale;
- 15 featured display names shown first, using entirely fictional abbreviated names such as `Demo A.`;
- 30 to 50 representative locations, subject to verification from public sources;
- 10 to 15 service areas or organisational units;
- 20 to 35 role families;
- 36 months of workforce history;
- sufficient vacancy, application, offer, onboarding, learning, PDR, absence and survey events to produce credible trends.

The exact number of locations and organisational entities must be driven by a documented public-source inventory. Unverified internal structures must be labelled as synthetic proxies.

### 7.2 Featured people

The first 15 names must be controlled through explicit metadata:

- `is_featured_demo_employee`;
- `display_order`;
- abbreviated `display_name`.

They must not be placed first through hidden alphabetical logic.

### 7.3 Reproducibility

Synthetic generators must support:

- `generation_seed`;
- `scenario_code`;
- generated timestamp;
- generator version;
- controlled scenario mode;
- exploratory random mode.

A controlled seed must reproduce the interview dataset.

### 7.4 Synthetic-data constraints

Generated data should include realistic but non-identifying variation in:

- service line;
- location;
- role family;
- pay band;
- employment type;
- contracted FTE;
- tenure;
- recruitment source;
- application status;
- offer outcome;
- onboarding outcome;
- PDR status;
- learning activity;
- internal move;
- promotion;
- leaver reason;
- protected-characteristic categories for aggregate equality analysis;
- survey participation and responses.

Do not generate real addresses, real email addresses, NHS numbers or names that intentionally correspond to identifiable SCAS staff.

---

## 8. Workforce Management mode

This mode is a limited operational data interface. It exists to demonstrate that analytical outputs respond to data changes.

### 8.1 Left navigation

- People Directory
- Employee Profile
- Contracts & FTE
- Organisational Assignments
- Vacancies
- Candidates
- Offers & Checks
- New Starters
- Learning & PDR
- Leavers
- Import / Export
- Audit History

### 8.2 Employee actions

The user must be able to:

- add a synthetic employee;
- edit permitted profile attributes;
- add a contract;
- change contracted hours or FTE;
- transfer an employee between organisational units;
- record an internal appointment or promotion;
- record PDR and learning events;
- mark an employee as a leaver;
- view effective-dated history.

Employees must not be physically deleted through the business UI. Leaving must set:

- `employment_status = 'Leaver'`;
- `leaving_date`;
- `leaving_reason`;
- effective end dates for active assignments or contracts.

### 8.3 Vacancy and candidate actions

The user must be able to:

- create and approve a vacancy;
- publish/close a vacancy in simulated workflow;
- create candidate applications;
- move applications through recruitment stages;
- record interview outcomes;
- create conditional offers;
- record acceptance or rejection;
- record pre-employment check status;
- confirm a start date;
- convert the successful candidate to a new starter;
- record probation outcome.

### 8.4 Validation examples

- FTE must be greater than 0 and normally no greater than 1.0, with documented exceptions.
- Contract end date must not precede start date.
- A candidate cannot start without an accepted offer.
- A vacancy cannot be filled beyond approved positions without an explicit over-establishment flag.
- A leaver cannot retain an open-ended current assignment after the leaving date.
- Foreign keys must resolve to active reference values.

---

## 9. Workforce Intelligence mode

### 9.1 Navigation

#### Executive

- Recruitment Overview
- Workforce Gap
- Recruitment Risks

#### Pipeline

- Vacancies
- Candidate Funnel
- Time to Hire
- Offers & Pre-employment Checks
- New Starters

#### Attraction

- Recruitment Channels
- Campaign Performance
- Candidate Experience
- University & Apprenticeship Pipeline

#### Workforce Outcomes

- Retention & Early Attrition
- Internal Progression
- Skills & Development
- Leaver Analysis

#### Equality & Assurance

- Inclusive Recruitment
- WRES Indicators
- Data Quality
- Metric Catalogue
- Sources & Assumptions

### 9.2 Executive KPI set

The first page must prioritise:

1. Open vacancies
2. Vacancy rate
3. Workforce gap in WTE
4. New starters
5. Median time to hire
6. Offer acceptance rate
7. Offer-to-start conversion
8. Early attrition within 12 months
9. Internal appointment rate
10. Recruitment likelihood ratio

Each KPI must show:

- current value;
- previous comparable period;
- target or reference value where applicable;
- direction of change;
- status;
- last refresh;
- data-quality status;
- hover tooltip with definition and worked calculation.

### 9.3 Recruitment funnel and vacancy lifecycle

**Do not mix vacancy counts with application/candidate counts in one conversion denominator.** A vacancy may receive many applications, and an individual application may progress through multiple dated stages. The UI must present two linked but mathematically distinct lifecycles.

#### A. Vacancy lifecycle (grain: approved vacancy/position)

1. Request submitted (where available)
2. Vacancy approved
3. Vacancy advertised
4. Vacancy closed or cancelled
5. Vacancy filled (only when the actual business event supports it)

Report approved/open/advertised/filled/cancelled vacancies and WTE, ageing, closure reasons, and time to fill. An administrative `Closed` status does not imply `Filled`. Reopened vacancies and partially filled multi-position vacancies must be handled explicitly.

#### B. Candidate/application funnel (grain: unique application per vacancy)

1. Application received
2. Eligibility screened
3. Shortlisted
4. Interviewed
5. Conditional offer
6. Offer accepted
7. Pre-employment checks completed
8. Start confirmed
9. Started
10. Probation completed

Required analysis:

- distinct applications entering or reaching each stage, with cohort date and unique entity grain disclosed;
- stage-to-stage conversion with numerator/denominator both representing the **same eligible application cohort**;
- withdrawal/rejection count and reason;
- median time spent at each stage, with clear treatment of pending/incomplete cases;
- results by service line, location, role, pay band, campaign and source;
- cohort comparisons over time and explicit stage eligibility/lag caveats;
- ability to drill from vacancy to its related applications without counting the vacancy itself as an application.

If the product displays a combined journey, it must use separate panels or a clearly labeled transition from the vacancy lifecycle into the application funnel, not a single misleading percentage conversion from `Vacancy approved` to `Applications received`.

Example: 10 advertised vacancies yield 250 valid applications, 40 interviews, 15 accepted offers and 12 starts. The 250 applications are **not** a 2,500% vacancy-to-application conversion; they are applications per advertised vacancy. The candidate application-to-start conversion is 12 / 250 = 4.8%, subject to the chosen cohort window.

---

### 9.4 Time-to-hire analysis

Separate calculations must include:

- request submitted to vacancy approved;
- vacancy approved to advertised;
- closing date to shortlist completed;
- shortlist to interview;
- interview to conditional offer;
- offer to checks completed;
- checks completed to start;
- approval to accepted offer;
- approval to actual start.

The UI must include a decomposition or stage-duration visual and must not collapse delays into a single unexplained number.

### 9.5 Vacancy and establishment analysis

Required metrics:

- budgeted establishment WTE;
- current substantive WTE;
- workforce gap WTE;
- vacancy headcount;
- vacancy WTE;
- vacancy rate;
- vacancy ageing;
- hard-to-fill vacancy rate;
- over/under establishment;
- critical-role vacancies;
- recruitment and vacancy closure status.

Required ageing bands:

- 0–30 days;
- 31–60 days;
- 61–90 days;
- 91–180 days;
- more than 180 days.

**Business rule:** distinguish *approved establishment positions*, *currently filled substantive WTE*, *approved open vacancy WTE* and *administrative vacancy closure*. Closing/cancelling a requisition without a genuine start or establishment reduction must not be reported as a newly filled position or an automatic improvement in workforce gap. Vacancy rate and establishment-gap definitions may use different denominators and need separate metric metadata.

For multi-position vacancies, store `approved_positions`, `approved_wte` and cumulative `filled_wte`; preserve partial fills and any permitted over-establishment flag. The effective-dated establishment baseline and assignment records must reconcile at selected `as_of_date`.

The demonstration must include two contrasting scenarios: **filled vacancy** (candidate starts and substantive WTE changes) and **cancelled vacancy** (requisition closes but no employee starts). KPI outcomes must reflect their actual effects.

---

### 9.6 Attraction channels

Support:

- NHS Jobs;
- Trac;
- careers site;
- university partnership;
- apprenticeship pathway;
- open day;
- employee referral;
- targeted digital campaign;
- community event;
- international recruitment;
- return-to-practice programme;
- other/unknown.

Metrics:

- applications;
- eligible applications;
- shortlisted;
- offers;
- starts;
- conversion rate;
- withdrawal rate;
- time to hire;
- cost per applicant where cost data exists;
- cost per hire where cost data exists;
- 6- and 12-month retention by source.

### 9.7 Candidate experience

Metrics:

- candidate satisfaction;
- communication rating;
- role-description clarity;
- interview-experience rating;
- percentage receiving timely updates;
- median response time;
- application abandonment;
- offer withdrawal reasons;
- candidate complaints;
- feedback response rate.

Candidate feedback must feed into People Voice and AI-assisted thematic analysis.

### 9.8 Inclusive recruitment

Analyse stage outcomes by permitted aggregate characteristics:

- applicant representation;
- shortlisting rate;
- interview rate;
- appointment rate;
- offer acceptance;
- stage conversion;
- recruitment likelihood ratio;
- unknown/not-declared rate.

Small-number suppression must be applied before response data leaves the API.

Default rules:

- do not show groups smaller than 5;
- use a threshold of 10 for sensitive survey breakdowns;
- prevent filter combinations that isolate an individual;
- display a suppression message instead of zero or blank data.

### 9.9 New-starter and onboarding analytics

Metrics:

- confirmed starters;
- did-not-start rate;
- check completion;
- induction completion;
- mandatory training completion;
- probation pass/extension rate;
- 30-, 90-, 180- and 365-day early attrition;
- time to competence where defined;
- new-starter satisfaction;
- quality-adjusted hire rate.

### 9.10 Retention and attrition

Metrics:

- turnover;
- retention;
- voluntary attrition;
- involuntary attrition;
- early attrition;
- attrition by tenure;
- positive progression;
- regrettable attrition;
- leavers by reason;
- internal versus external moves;
- hires-to-leavers ratio;
- net workforce movement.

### 9.11 Internal progression and development

Metrics:

- internal appointment rate;
- promotion rate;
- employee moves between roles;
- months in current role;
- months since latest promotion;
- PDR compliance;
- development-objective completion;
- access to learning;
- apprenticeship completion;
- student-to-qualified conversion;
- professional qualification expiry risk;
- positive progression versus unwanted attrition.

`Months since promotion` must never be presented as evidence of unfairness in isolation. It must be interpreted alongside role tenure, available pathways, PDR, completed development, applications and opportunity availability.

---

## 10. Metric catalogue and tooltips

Every material KPI must have one canonical definition in a metric catalogue.

### 10.1 Required metadata

- metric code;
- display name;
- business definition;
- formula;
- numerator;
- denominator;
- exclusions;
- grain;
- valid dimensions;
- source tables;
- data owner;
- refresh frequency;
- target/benchmark;
- quality rule;
- interpretation caveat;
- version and effective date.

### 10.2 Tooltip example

**Offer acceptance rate**

> Accepted offers ÷ all offers made × 100  
> Accepted offers: 82  
> Offers made: 100  
> Result: 82.0%  
> Excludes withdrawn offers cancelled by the organisation before candidate response.  
> Last refreshed: [timestamp]  
> Data quality: 98.9%

### 10.3 Core formulas

- `Vacancy rate = vacant approved WTE / budgeted establishment WTE × 100`
- `Offer acceptance rate = accepted offers / valid offers made × 100`
- `Offer-to-start conversion = starters / accepted offers × 100`
- `Application-to-start conversion = starters / valid applications × 100`
- `Early attrition 12m = eligible starters from the measured cohort who leave within 365 days / all starters in that same cohort with a complete 365-day observation window × 100`
- `Internal appointment rate = internal appointments / all appointments × 100`
- `Retention rate = employees retained throughout period / eligible employees at period start × 100`
- `Time to hire = accepted-offer date − vacancy-approval date`
- `Time to start = actual-start date − vacancy-approval date`

Definitions must clarify headcount versus WTE, period versus point-in-time metrics, cohort eligibility, event timing and observation windows. `Vacancy closed` is not equivalent to `Vacancy filled`, and recruitment conversion rates must never mix vacancy grain and application grain.

When a denominator is zero or cohort follow-up is insufficient, the API returns a typed unavailable result rather than `0`, `NaN` or `Infinity`. Tooltips must show numerator, denominator, exclusions, date window, calculation version and synthetic-data caveat.

---

## 11. People Voice mode

### 11.1 Navigation

- Survey Dashboard
- Survey Builder
- Question Bank
- Campaigns
- Response Monitor
- Report Analysis
- Analyst Review
- Action Tracker

### 11.2 Survey builder

Allow users to define:

- campaign name and ID;
- audience;
- start/end dates;
- questions;
- rating scales;
- free-text questions;
- anonymity threshold;
- analytical taxonomy version;
- scenario and generation seed.

### 11.3 Synthetic response generator

Provide buttons:

- **Generate balanced sample**
- **Generate emerging concern**
- **Generate significant concern pattern**
- **Generate random exploratory sample**

Generation controls:

- response count;
- analysable-text proportion;
- positive/neutral/negative mix;
- theme prevalence;
- concern severity;
- ambiguous-response proportion;
- emerging-theme count;
- period;
- service lines;
- generation seed.

The generator must distinguish:

- prevalence: how often a theme appears;
- severity: how serious a potential issue may be.

One severe comment must not be presented as statistically prevalent.

### 11.4 Survey representativeness, weighting and segment analysis

The survey module must distinguish between **representation adjustment**, **segment analysis**, and **signal prioritisation**. These are separate analytical operations and must not be combined into one opaque score.

#### 11.4.1 Representation weighting

Where a survey sample does not reflect the known workforce population, the system may calculate a post-stratification weight:

`representation_weight = population_share_of_group / respondent_share_of_group`

Example:

- a staff group represents 30% of the eligible workforce;
- it represents 15% of valid survey respondents;
- its untrimmed representation weight is `30 / 15 = 2.0`.

Requirements:

- weighting variables must be selected from approved dimensions such as service line, role family, location group, tenure band or employment type;
- weighting must be based on known population totals and documented in the Metric Catalogue;
- weights must be trimmed to a configurable range, default `0.5–2.0`, to prevent small groups dominating the result;
- both weighted and unweighted results must be available to the analyst;
- the effective sample size after weighting must be calculated and displayed;
- weighting must not be presented as correcting question-design bias, social-desirability bias, inaccurate answers or organisational silence;
- a result must be labelled `Unweighted`, `Weighted`, or `Weighting not available`;
- the UI must display: **Survey weights correct group representation, not the truthfulness or importance of an individual opinion.**

#### 11.4.2 Required survey segmentation dimensions

Where privacy thresholds permit, survey analysis must support segmentation by:

- service line;
- organisational unit;
- grouped location;
- role family;
- pay band;
- clinical/non-clinical grouping;
- employment type;
- FTE band;
- tenure band;
- months in current role band;
- recent promotion flag;
- recently qualified flag;
- qualification type or qualification group;
- new-starter cohort;
- leaver cohort where an exit survey exists;
- recruitment source;
- PDR status;
- learning participation;
- protected-characteristic group for authorised equality analysis.

The system must not automatically assign greater value to an individual response because the respondent is more senior, more highly paid, longer-serving, recently promoted or more highly qualified. These attributes are segmentation variables, not measures of truth or personal importance.

#### 11.4.3 Segment signal measures

For each approved segment and theme, calculate where data permits:

- unique responses mentioning the theme;
- analysable responses in the segment;
- unweighted theme prevalence;
- weighted theme prevalence;
- difference from the organisation-wide result in percentage points;
- prevalence ratio against the comparison population;
- period-on-period change;
- minimum-group suppression status;
- effective sample size;
- linked workforce indicators, without claiming causation.

Example presentation:

> 24% of analysable responses from employees qualified within the last 12 months mentioned limited development opportunities, compared with 9% among other eligible respondents. Early attrition also increased in the same cohort. This is an analytical signal requiring review and does not establish causation.

#### 11.4.4 Signal Review Priority

The product may calculate a transparent **Signal Review Priority** to determine the order in which findings should be reviewed. It must not be called an employee risk score, probability, confidence score or measure of respondent value.

Default components:

- prevalence: 30%;
- severity: 30%;
- strategic relevance: 20%;
- segment concentration: 10%;
- trend change: 10%.

`review_priority = prevalence_component × 0.30 + severity_component × 0.30 + strategic_relevance_component × 0.20 + segment_concentration_component × 0.10 + trend_change_component × 0.10`

Requirements:

- each component must use a documented 0–100 scale;
- component values and formula must be visible in a tooltip;
- configuration and version must be stored;
- serious safety, safeguarding, discrimination or Freedom to Speak Up signals may override the numeric order and require priority human review;
- job title, pay band, seniority or qualification level must not independently increase the priority score;
- AI may classify evidence, but the backend must calculate the priority using governed rules;
- the score is for review triage only and must not trigger an employment decision.

#### 11.4.5 Triangulation measures

A signal may be strengthened for human investigation when it is observed alongside independent workforce measures for the same cohort or period, including:

- early attrition;
- retention;
- voluntary turnover;
- internal applications;
- internal appointment rate;
- months in role;
- months since promotion;
- PDR compliance;
- learning participation;
- qualification completion;
- vacancy status of the relevant role;
- hard-to-fill role status;
- exit-survey themes;
- candidate or new-starter feedback.

The system must use wording such as `observed alongside`, `associated with`, or `requires further investigation`. It must not state that a survey theme caused a workforce outcome unless a separate validated causal design supports that claim.

### 11.5 Demonstration reports

#### Report 1: prebuilt and reviewed

**Rota Changes and Workforce Pressure**

- already populated;
- already analysed;
- analyst-reviewed;
- includes evidence IDs;
- includes charts;
- includes at least one linked management action;
- available if the external AI service is unavailable.

#### Report 2: generated on demand

**Career Development and Progression**

Themes may include learning access, PDR, transparent progression, time in role and inconsistent opportunities.

#### Report 3: generated on demand

**Wellbeing and Communication**

Themes may include workload, management communication, recognition, psychological safety, Freedom to Speak Up and improvement ideas.

### 11.6 Report Analysis page

The page must contain two sections.

#### AI-identified signals panel

Example wording:

> **AI analysis identified a strong signal of [theme]. Analyst review is recommended.**

Alternative levels:

- `Possible signal`
- `Moderate signal`
- `Strong signal`
- `Potentially serious signal — priority human review required`

The system must not describe these labels as statistically calibrated probabilities.

Each signal card must show:

- signal label;
- theme;
- classification;
- unique responses mentioning the theme;
- percentage of analysable responses;
- survey ID;
- analysis ID and date;
- analyst-review state;
- evidence link;
- `Send for analyst review` action.

#### Survey report list

Show:

- survey title and ID;
- reporting period;
- total responses;
- analysable comments;
- count of AI-identified signals;
- priority flags;
- review status;
- latest analysis timestamp.

Opening a report must display:

- concise AI summary;
- key signals;
- complaints, concerns, suggestions, initiatives and positive feedback;
- theme-frequency chart;
- signal severity/prevalence view;
- evidence response IDs;
- limitations;
- review history;
- linked management actions.

---

## 12. AI-assisted analysis

### 12.1 Principle

AI identifies signals and organises evidence. It does not establish statistical validity, causation, employee culpability or a final workforce decision.

Permanent report notice:

> **AI-identified signals require analyst review before operational or workforce decisions are made.**

### 12.2 Analysis pipeline

1. Select an eligible survey campaign.
2. Validate response count and anonymity threshold.
3. remove or redact prohibited identifiers;
4. split comments into analysable units if required;
5. classify each response;
6. aggregate response-level classifications into themes;
7. validate model output against a strict schema;
8. reject references to unknown response IDs;
9. store versioned draft findings;
10. place findings into analyst review;
11. publish only confirmed or amended findings to Gold views.

### 12.3 Unit of analysis

The system must support:

- one survey response containing zero, one or multiple themes;
- one theme appearing in many responses;
- sentence-level evidence where a comment contains multiple subjects.

The relationship between responses and themes is many-to-many.

### 12.4 Controlled taxonomy

Approved top-level themes:

- Workload and capacity
- Rostering and working hours
- Recruitment process
- Candidate communication
- Onboarding
- Leadership and management
- General communication
- Wellbeing
- Psychological safety
- Freedom to Speak Up
- Learning and development
- Career progression
- Inclusion and fairness
- Equipment and systems
- Recognition
- Staff or patient safety

Classifications:

- Complaint
- Concern
- Safety concern
- Suggestion
- Improvement initiative
- Positive feedback
- Request for clarification
- Neutral observation

The AI may propose an `emerging_theme`, but it must remain distinct from the controlled taxonomy until reviewed.

### 12.5 Structured output

The AI connector must return JSON conforming to a Pydantic model. Minimum conceptual structure:

```json
{
  "analysis_id": "AN-2026-0042",
  "survey_id": "PV-2026-Q3",
  "summary": "Recurring concerns were identified around short-notice rota changes.",
  "signals": [
    {
      "theme": "Rostering and working hours",
      "subcategory": "Late rota changes",
      "classification": "Complaint",
      "signal_level": "Strong",
      "severity": "Medium",
      "response_ids": ["R-104", "R-119", "R-127"],
      "unique_response_count": 3,
      "summary": "Several responses describe short-notice rota changes.",
      "human_review_required": true
    }
  ]
}
```

### 12.6 Employee silence and non-response limitations

The analysis must explicitly recognise that employees who respond may differ systematically from employees who do not respond, and that some employees may choose not to raise concerns. The product must therefore expose, where data permits:

- eligible population;
- invitations issued;
- response rate;
- response rate by approved segment;
- item non-response rate;
- analysable free-text rate;
- represented and under-represented segments;
- exit-survey coverage;
- weighting availability and limitations.

The product must not infer that non-respondents are satisfied, dissatisfied or intending to leave. It must not claim that high-performing or highly qualified employees generally leave quietly unless supported by the analysed data.

### 12.7 Counting rules

Keep separate:

- total responses;
- analysable responses;
- unique responses mentioning a theme;
- individual theme mentions;
- estimated incidents, only when evidence genuinely represents distinct incidents.

Preferred presentation:

> **14 of 126 analysable responses mentioned late rota changes (11.1%).**

Do not label all mentions as complaints or incidents unless classification supports that wording.

### 12.8 Review workflow

Statuses:

1. Draft
2. AI analysis completed
3. Awaiting analyst review
4. Confirmed
5. Amended
6. Rejected
7. Published
8. Action created
9. Closed

The analyst must be able to:

- change classification;
- amend theme and subtheme;
- merge or split themes;
- change severity;
- exclude false positives;
- record rationale;
- approve publication;
- create a management action.

Keep both:

- AI-produced classification;
- analyst-reviewed classification.

### 12.9 Serious signals

Categories requiring priority review:

- staff safety;
- patient safety;
- safeguarding;
- harassment or discrimination;
- potential fraud;
- serious psychological distress;
- Freedom to Speak Up concerns.

For these categories, the AI must:

- flag priority human review;
- cite source response IDs;
- avoid accusations or identification of a responsible person;
- not close the case;
- not send automatic messages;
- not initiate an employment process.

### 12.10 AI traceability

Store:

- analysis ID;
- survey ID;
- provider;
- model name;
- prompt version;
- taxonomy version;
- timestamp;
- model parameters where available;
- input hash;
- generation seed where relevant;
- response IDs included in the request;
- raw structured response;
- validation result;
- review state;
- reviewer and review timestamp;
- superseding analysis ID.

### 12.11 AI output validation

Backend rules:

- reject malformed JSON;
- reject unknown taxonomy values unless marked as emerging;
- reject invented response IDs;
- reject missing evidence for material findings;
- prevent publication when response counts violate suppression rules;
- detect duplicate signals;
- enforce request and token-size limits;
- record partial and failed analyses.

### 12.12 Fallback behaviour

If the AI API times out or fails:

- show a concise error;
- retain source responses;
- do not create a false successful analysis;
- offer retry;
- allow a prevalidated demonstration result for the nominated scenario;
- label fallback output as `Demonstration fallback result`;
- record the fallback in audit history.

---

## 13. Insight Pilot

### 13.1 Purpose

Insight Pilot is a context-aware analytical assistant displayed beside relevant charts and reports.

It must answer controlled analytical requests such as:

- Show the five service lines with the highest vacancy rate.
- Compare time to hire by role family.
- Where do candidates leave the funnel?
- Compare offer acceptance by recruitment source.
- Show early attrition for the latest starter cohorts.
- Summarise candidate-experience themes.
- Which metrics currently have low data quality?
- Explain how vacancy rate is calculated.

### 13.2 Response requirements

Every answer must include, where applicable:

- result;
- filters used;
- period;
- metric definition;
- data-quality caveat;
- reference to the relevant report/page;
- evidence IDs for survey analysis;
- limitation against causal interpretation.

### 13.3 Implementation approach

Prefer a controlled semantic-intent layer for common commands. The language model may generate narrative, but metric calculation must occur through approved backend queries or Gold views.

The AI must not create unverified SQL and execute it against the database without an allowlist, query validation and row/column restrictions.

---

## 14. Forecasting and scenario planning

### 14.1 Forecast scope

Forecast only workforce and recruitment measures, such as:

- vacancy WTE;
- recruitment starts;
- time to hire;
- early attrition;
- workforce establishment gap;
- applicant pipeline volume.

Do not forecast emergency call volumes or ambulance operational performance in this product.

### 14.2 Chart behaviour

Charts supporting forecasting must include a toggle:

> **Enable forecast**

When enabled:

- historical actuals use a solid line;
- forecast uses a dashed line;
- forecast start is visibly marked;
- an interval band is shown where the method supports it;
- model name is displayed;
- training period and forecast horizon are disclosed;
- model error or validation metric is shown;
- assumptions are available in a tooltip or panel.

### 14.3 Candidate methods

For PoC:

- seasonal-naive baseline;
- exponential smoothing;
- linear trend/regression where justified.

The selected model should be compared with a baseline. Forecasts based on synthetic data must be labelled illustrative.

### 14.4 Scenario controls

Allow adjustment of:

- vacancies approved per month;
- applicants per vacancy;
- stage conversion rates;
- time for pre-employment checks;
- offer acceptance;
- planned starts;
- early attrition;
- internal appointments;
- forecast horizon.

Outputs:

- expected starts;
- expected vacancy WTE;
- expected workforce gap;
- expected time to fill;
- uncertainty/assumption statement;
- comparison with baseline.

---

## 15. Management action tracker

A confirmed finding or analytical observation may create an action containing:

- action ID;
- source report or metric;
- description;
- owner;
- created date;
- due date;
- baseline;
- target;
- status;
- expected benefit;
- progress notes;
- closure evidence.

AI may draft an action for review but must not assign a person, send a notification or publish the action automatically.

---

## 16. Data architecture

### 16.1 System boundaries and logical flow

The project uses a **shared identity/control plane** and a **project-owned analytical/data plane**.

```text
Browser → Next.js host (Vercel)
  ├─ /portfolio (host catalogue)
  └─ /portfolio/workforce-intelligence (protected route + SPA UI)
         │ first-party authenticated session
         ▼
     narrow Next.js BFF / server adapter
         │ fixed backend origin; signed Firebase session forwarded server-to-server
         ▼
FastAPI host (Render) ── independently verify identity + Workforce grant
         │
         ▼
Workforce router / service layer / domain validation
         │
         ▼
Workforce-owned SQLite (operational writes + audit, disposable)
         │
         ▼
Approved ingestion projection → Bronze → Silver → Gold
         │
         ├─ dashboards / metric catalogue / quality / exports
         ├─ forecasts / scenario evaluations
         └─ approved query intents / Insight Pilot / reviewed AI signals
```

Separately:

```text
Firebase Authentication + shared Firestore control plane
    → platform identity, admission and per-project grant decisions
    → security policy and durable central audit
    ≠ Workforce SQLite
    ≠ Fleet SQLite
```

The four Workforce modes share this internal architecture; they must not import Fleet's SQLite store or its domain services. The AI connector is invoked through an approved interface; no direct AI API secrets or unrestricted SQL go to the browser.

### 16.2 Data minimisation

Data minimisation must occur before analytical ingestion. The Bronze layer contains only fields approved for the analytical use case while preserving the received structure and granularity of approved fields. Externally submitted AI payloads are separately minimized and redacted.

### 16.3 Restricted source zone

If source-like records are illustrated, identify a logically restricted source zone containing minimal raw ingestion records. Source-level and analytical visibility are conceptually distinct even though all users have the same *project* access level; this synthetic demo does not claim production-grade confidential HR segregation.

### 16.4 Bronze layer

Purpose:

- approved source fields with minimal transformation;
- source granularity preserved;
- technical metadata added;
- rejected data retained in quarantine rather than silently removed.

Metadata:

- source record ID;
- source system;
- ingestion timestamp;
- batch ID;
- schema version;
- record hash;
- validation status.

### 16.5 Silver layer

Purpose:

- corrected data types;
- conformed role, service-line, location and status values;
- duplicate handling;
- surrogate keys;
- effective-dated history;
- validated relationships;
- standard business rules;
- redaction/pseudonymisation where required.

### 16.6 Gold layer

Purpose:

- star schema;
- canonical KPI logic;
- workforce monthly snapshots;
- recruitment funnel facts (application grain separated from vacancy grain);
- cohort outcomes;
- published survey findings;
- forecast results;
- data-quality indicators;
- aggregate suppression.

Only reviewed and explicitly confirmed or amended survey findings may enter published Gold views. Confirmed means a human review event, not a privileged user tier.

### 16.7 Architecture mode pages

- Architecture Overview
- Bronze / Silver / Gold
- Data Model
- Data Lineage
- Data Quality
- Metric Catalogue
- Sources & Assumptions
- BPMN

Each layer page must show:

- purpose;
- permitted content;
- example table;
- example row;
- changes from prior layer;
- owner;
- quality status.

### 16.8 Implementation form for the PoC

Bronze/Silver/Gold are **logical governed layers**; a dedicated cloud data lake or Fabric deployment is not required. They may be implemented in project-owned SQLite tables/views and deterministic Python transformations, provided that lineage, refresh/version semantics and row-level reconciliation are real and testable. Do not label arbitrary frontend arrays as a functioning data pipeline.

- Operational tables retain authoritative mutable synthetic records.
- Bronze ingestion snapshots or approved staging tables preserve source grain and batch metadata.
- Silver provides conformed, validated, effective-dated entities.
- Gold provides validated dimensional facts/aggregates; the canonical metric implementation is in one server-side location, referenced by UI, Insight Pilot and exports.
- A business mutation invalidates or recomputes only affected projections. Avoid silently stale Gold results.
- Each dataset refresh exposes an `as_of` timestamp, seed/scenario version and current `dataset_generation`.

### 16.9 Persistence and failure isolation

- Use a **dedicated Workforce SQLite file**, schema migration history, immutable seed or deterministic generator, separate from Fleet's file and bootstrap.
- Use SQLite transactions for committed imports and multi-table domain commands.
- Avoid sharing sessions/connections across request boundaries incorrectly; use the project's own scoped persistence adapter.
- Preserve foreign-key checks, unique constraints, indexes and effective-date invariants.
- Project bootstrap must be optional to the host: a Workforce database error cannot fail public Chat, Resume, Contact, or Fleet initialization.
- Render restart may lose modifications. Regeneration must yield a known good scenario, and client state must detect generation changes.
- Never put durable platform grants/credentials/policies inside the disposable project database.

---

## 17. Data model

### 17.1 Operational tables

Minimum tables:

- `employees`
- `employment_contracts`
- `organisation_assignments`
- `organisational_units`
- `locations`
- `roles`
- `vacancies`
- `recruitment_campaigns`
- `candidate_applications`
- `application_stage_events`
- `interviews`
- `offers`
- `pre_employment_checks`
- `starter_events`
- `probation_events`
- `learning_events`
- `pdr_events`
- `promotion_events`
- `leaver_events`
- `survey_campaigns`
- `survey_questions`
- `survey_responses`
- `survey_response_themes`
- `ai_analyses`
- `ai_signals`
- `analyst_reviews`
- `management_actions`
- `audit_events`
- `import_batches`
- `data_quality_issues`
- `forecast_runs`
- `forecast_results`

### 17.2 Analytical dimensions

- `dim_date`
- `dim_employee`
- `dim_organisation`
- `dim_location`
- `dim_role`
- `dim_pay_band`
- `dim_contract_type`
- `dim_recruitment_source`
- `dim_candidate_stage`
- `dim_campaign`
- `dim_survey`
- `dim_question`
- `dim_theme`
- `dim_metric`

### 17.3 Analytical facts

- `fact_employee_monthly_snapshot`
- `fact_contract_history`
- `fact_vacancy_snapshot`
- `fact_application`
- `fact_application_stage_event`
- `fact_offer`
- `fact_new_starter`
- `fact_probation`
- `fact_learning`
- `fact_pdr`
- `fact_internal_progression`
- `fact_leaver`
- `fact_survey_response`
- `fact_reviewed_survey_signal`
- `fact_management_action`
- `fact_forecast`
- `fact_data_quality_issue`

### 17.4 Effective-dated history

For contracts, assignments, roles and other changing attributes, store:

- `valid_from`;
- `valid_to`;
- `is_current`;
- `created_at`;
- `created_by`;
- `change_reason`.

Use a simplified Slowly Changing Dimension Type 2 pattern where analytical history is required.

### 17.5 Audit data

Every material mutation must record:

- event ID;
- entity type and key;
- action;
- timestamp;
- authenticated user;
- old-value snapshot or diff;
- new-value snapshot or diff;
- source channel;
- correlation ID;
- demo session ID.

---

### 17.6 Ownership, keys and event invariants

- All tables listed above belong to `workforce_intelligence`; there is no `fleet_hub` foreign key, import or shared SQLite attachment.
- The operational `vacancies` entity must distinguish open, filled, cancelled and administrative closure outcomes, approved positions and WTE, and effective dates.
- `candidate_applications` is uniquely tied to its application ID and a vacancy ID. Funnel facts are at application/event grain, **not** vacancy grain.
- `starter_events` must relate to a valid accepted offer and an effective employment/assignment event where applicable.
- Repeated stage events must not double-count a distinct application reaching one stage.
- Effective-dated current records must not overlap illegally; record versioning is necessary for concurrency checks.
- Add internal metadata as needed: `dataset_generation`, `seed_version`, `scenario_code`, `import_batch_id`, `source_row_hash`, `updated_at`, and `record_version`.
- Audits of Workforce demo changes are disposable with the Workforce database. Central identity/grant/security audits are durable and platform-owned.
- Not every full-scope table needs to be created in the first MVP migration. Migrations follow delivered vertical slices and must remain reversible or have documented recovery behavior.

---

## 18. Excel import and export

### 18.1 Import workflow

1. Download template.
2. Upload workbook.
3. Validate file type and size.
4. Parse into staging structures.
5. Validate schema and business rules.
6. Present row-level errors and warnings.
7. Preview inserts, updates and unchanged rows.
8. Confirm import.
9. Write within a database transaction.
10. Create an audit entry.
11. Recalculate affected analytical views.
12. Present dashboard impact.

Technical contract:

- Authenticate and authorize **before** parsing or persisting the upload.
- Apply bounded upload limits, workbook structure validation, supported sheet name/version checks, and spreadsheet formula-safety measures for export.
- Generate a stable import batch ID and idempotency key, and prevent duplicate commits of the same confirmed batch.
- Use only project-owned staging areas; do not reuse Fleet's import pipeline or DB.
- Match rows by documented business keys and effective dates; report insert/update/no-op counts before confirmation.
- One confirmed import writes source changes, audit and batch status atomically or records a recoverable failure state without partial business mutation.
- Rebuild or invalidate affected Silver/Gold projections and expose the new dataset version.
- Reject stale preview confirmations after a reset or incompatible intervening database version.

### 18.2 Workbook sheets

- `Employees`
- `Contracts`
- `Assignments`
- `Vacancies`
- `Applications`
- `Offers`
- `PreEmploymentChecks`
- `NewStarters`
- `Learning`
- `PDR`
- `Leavers`
- `SurveyResponses`
- `ReferenceData`

### 18.3 Import result

Example:

- 43 valid records;
- 3 warnings;
- 2 rejected rows;
- 4 new people;
- 7 contract changes;
- 1 unknown location code.

### 18.4 Export

Support authorised export of:

- filtered analytical results;
- metric catalogue;
- data-quality issues;
- survey findings with permitted evidence;
- import-error reports;
- synthetic source templates.

Exports must identify the dataset as synthetic demonstration data.

---

## 19. Data quality

### 19.1 Quality dimensions

- completeness;
- validity;
- uniqueness;
- consistency;
- timeliness;
- referential integrity;
- reconciliation.

### 19.2 Example rules

- employee has a valid current contract when status is active;
- assignment references a valid organisational unit;
- contract end date is not earlier than start date;
- FTE is within an approved range;
- accepted offer references an active application;
- starter references an accepted offer;
- application stage dates are chronological;
- vacancy filled WTE does not exceed approved WTE without flag;
- AI evidence IDs exist in the submitted payload;
- published survey signals passed analyst review;
- suppressed groups never appear in API responses.

### 19.3 Quality presentation

Show:

- issue count by severity;
- pass rate by quality dimension;
- affected entity/table;
- trend;
- owner;
- resolution status;
- impact on metrics.

Dashboards must show a quality badge and must not imply precision when material quality failures exist.

---

## 20. Sources and assumptions

Create a visible register containing:

- item;
- value or structural assumption;
- type: public source / synthetic / modelling assumption;
- source publication and date;
- URL or document reference;
- date accessed;
- implementation use;
- limitations.

Examples:

- organisational workforce scale: public source;
- service-line names: public source;
- employee records: synthetic;
- organisational hierarchy: demonstration assumption;
- KPI values: synthetic unless explicitly shown as context;
- survey comments: AI-generated synthetic;
- forecasts: illustrative demonstration output.

Public SCAS sources currently relevant to the specification include:

- SCAS People Strategy 2023–2026;
- SCAS Annual Report and Accounts 2025/26;
- SCAS Workforce Race Equality Standard reporting;
- SCAS public performance and Board-reporting pages where workforce content is present.

---

## 21. BPMN requirement

### 21.1 Primary process

Create an interactive or zoomable BPMN diagram for **People Voice to Action**.

### 21.2 Swimlanes

- Employee / Candidate
- People Team
- Data & Analytics
- AI Service
- Analyst Reviewer
- Manager / Action Owner
- Governance

### 21.3 Process

1. Create survey.
2. Approve questions.
3. Publish campaign.
4. Collect responses.
5. Apply data minimisation/redaction.
6. Validate anonymity threshold.
7. Run AI thematic analysis.
8. Validate structured output and evidence IDs.
9. Send signals for analyst review.
10. Confirm, amend or reject findings.
11. Publish approved findings.
12. Create action.
13. Monitor target and progress.
14. Communicate outcome.
15. Close feedback loop.

### 21.4 Error paths

Include:

- insufficient response count;
- AI API failure;
- invalid JSON;
- unsupported evidence;
- urgent-human-review signal;
- analyst rejection;
- action overdue.

---

## 22. API requirements and host transport

### 22.1 Canonical API namespace

**All Workforce business routes are namespaced under `/api/workforce`** to prevent collisions with the host's existing `/api/*` rewrite, public RAG, Contact, and Fleet's `/api/vor/*` endpoints. The paths below are indicative domain contracts, not an instruction to move existing host endpoints.

#### Workforce

- `GET /api/workforce/employees`
- `POST /api/workforce/employees`
- `GET /api/workforce/employees/{id}`
- `PATCH /api/workforce/employees/{id}`
- `POST /api/workforce/employees/{id}/contracts`
- `POST /api/workforce/employees/{id}/assignments`
- `POST /api/workforce/employees/{id}/leave`

#### Recruitment

- `GET /api/workforce/vacancies`
- `POST /api/workforce/vacancies`
- `PATCH /api/workforce/vacancies/{id}`
- `POST /api/workforce/applications`
- `POST /api/workforce/applications/{id}/stage-events`
- `POST /api/workforce/offers`
- `PATCH /api/workforce/offers/{id}`
- `POST /api/workforce/starters`

#### Analytics

- `GET /api/workforce/analytics/executive`
- `GET /api/workforce/analytics/vacancy-lifecycle`
- `GET /api/workforce/analytics/candidate-funnel`
- `GET /api/workforce/analytics/time-to-hire`
- `GET /api/workforce/analytics/retention`
- `GET /api/workforce/analytics/progression`
- `GET /api/workforce/metrics`
- `GET /api/workforce/data-quality`

#### Survey weighting and segment analysis

- `POST /api/workforce/surveys/{id}/weighting-runs`
- `GET /api/workforce/surveys/{id}/weighting-runs/{run_id}`
- `GET /api/workforce/surveys/{id}/segment-results`
- `GET /api/workforce/surveys/{id}/representativeness`
- `POST /api/workforce/analyses/{id}/priority`
- `GET /api/workforce/analyses/{id}/priority`

#### Surveys and AI

- `POST /api/workforce/surveys`
- `POST /api/workforce/surveys/{id}/generate-responses`
- `GET /api/workforce/surveys/{id}/responses`
- `POST /api/workforce/surveys/{id}/analyse`
- `GET /api/workforce/analyses/{id}`
- `POST /api/workforce/analyses/{id}/review`
- `POST /api/workforce/analyses/{id}/publish`
- `POST /api/workforce/analyses/{id}/actions`
- `POST /api/workforce/insight-pilot/query`

#### Import/export

- `GET /api/workforce/import/template`
- `POST /api/workforce/import/validate`
- `POST /api/workforce/import/commit`
- `GET /api/workforce/import/{batch_id}/errors`
- `POST /api/workforce/export`

#### Forecast/scenario

- `POST /api/workforce/forecast`
- `POST /api/workforce/scenarios`
- `GET /api/workforce/scenarios/{id}`

#### Demo controls

- `POST /api/workforce/demo/reset`
- `POST /api/workforce/demo/seed`
- `GET /api/workforce/demo/status`

### 22.2 Same-origin browser access and BFF

The existing `frontend/next.config.mjs` rewrites `/api/:path*` to Render. An ordinary Next.js page guard alone cannot secure direct Render access, and a first-party Next.js `HttpOnly` cookie does not automatically reach the Render hostname.

Recommended request path for authenticated Workforce operations:

1. The SPA calls a **narrow same-origin Workforce BFF** route owned by the Next.js host, for example `/portfolio/workforce-intelligence/api/*`. This route must not collide with the global `/api/*` rewrite.
2. Next.js verifies the existing Firebase website session and the platform admission policy; it applies CSRF/Origin protections for state-changing browser operations.
3. The BFF forwards the signed Firebase session server-to-server to an **allowlisted fixed `BACKEND_ORIGIN`** using the already established `Authorization: FirebaseSession` contract; it must never forward credentials to a browser-supplied URL.
4. FastAPI independently validates the signed session/revocation and **checks the current `workforce_intelligence` grant/capability on each protected operation**, including direct Render requests.
5. The Workforce router validates the payload through Pydantic, executes project-owned business logic, and emits project-local audit records for mutations.

The first merged Firebase increment currently contains an identity probe (`/api/lab/identity`) and server-side transport, not a generic project-authorized Workforce BFF. Adapt the proven pattern without misusing the identity probe as a business authorization dependency. Centralize the shared BFF mechanics rather than duplicating security-sensitive token parsing in each feature.

### 22.3 API invariants and errors

- **Every** Workforce endpoint that discloses protected project data, including GET, file downloads, scenario status, exports and AI responses, requires current project membership; write endpoints also enforce operation safety.
- No bearer token, Firebase identity, Owner email, client-side flag, or successful Lab login alone is sufficient to grant access to the Workforce project.
- All mutations use validated request schemas and emit correlation IDs and audit events.
- Use pagination/filter allowlists and bounded response sizes for tables and detailed reports.
- Prefer meaningful HTTP semantics: `401` unauthenticated, `403` authenticated without project grant, `409` stale dataset/record-version conflict, `422` invalid business input, `429` throttled, `503` dependent authorization/AI service unavailable. Do not expose secrets or internal exceptions.
- Idempotency is mandatory for retryable import commitments, AI analysis dispatch and reset actions; document expected behavior under a repeated request.
- Response metadata includes calculation/as-of timestamps and a dataset generation/version when relevant.
- FastAPI's OpenAPI contract is the source of truth for request/response types; project frontend DTOs should be generated from or contract-tested against that schema to prevent TypeScript/Pydantic drift.

---

## 23. Security, privacy and responsible use

### 23.1 Authentication and authorization

- Reuse Firebase Authentication and the existing Owner-provisioned email/password flow; do not create a Workforce credential store.
- Reuse the platform's secure `HttpOnly` website session, recent-login/admission policy and expiry/revocation handling. OAuth providers are **not a requirement for this project's release**.
- Check explicit shared-project membership for `workforce_intelligence` in both Next.js protected-route handling and FastAPI protected API handling. **All application Members have the same effective access**; do not create project role tiers.
- The platform `Owner` may provision or revoke accounts/grants through central mechanisms; this is outside Workforce's business authorization.
- Missing grant, revoked identity, expired session, unavailable Firestore authorization state or disabled project must fail closed.
- Never trust hidden UI controls, JavaScript claims, browser-submitted `role`, email strings, `X-User-*` headers or an Origin header as proof of identity.
- Ensure direct Render requests cannot bypass any Workforce authorization decision.

### 23.2 Application security

- parameterised queries or ORM;
- CSRF/Origin controls on cookie-authenticated mutation routes and BFF calls;
- fixed allowlisted backend origin for credential forwarding;
- secure response headers and no-store caching of protected data;
- rate limiting for AI, reset and file-upload endpoints;
- maximum upload size and explicit workbook validation;
- file type, content and worksheet-schema validation;
- input-length limits, pagination and safe exports;
- output encoding and formula-injection protection for exported spreadsheets;
- secrets stored only in server environment/managed secrets, never in the repository or client bundle;
- no AI API key or Firebase Admin service-account key exposed to browser code;
- project-local CORS assumptions must not replace authorization;
- deny-all browser Firestore access rules remain intact for control-plane collections; privileged Admin SDK operations enforce server-side rules.

### 23.3 AI privacy contract

Before external AI submission:

- remove names;
- remove email, telephone and address data;
- remove employee IDs;
- use survey response IDs;
- generalise small-group attributes;
- redact accidental identifiers in free text;
- send only required question and taxonomy context.

All demonstration records are synthetic, but the redaction pipeline must still run to demonstrate a governed pattern. No actual confidential employee or patient information may be introduced. Never send raw platform session credentials or private repository secrets to the AI provider.

### 23.4 Demo disclosures

Display:

- synthetic-data notice;
- unofficial-product notice;
- possible periodic **Workforce database** reset notice;
- AI-human-review notice;
- illustrative-forecast notice;
- no claim that current SCAS figures are calculated from synthetic records.

### 23.5 Operational boundaries

- A reset, seed or import can change only Workforce's disposable SQLite/data projections and project-local audit records.
- No Workforce endpoint may alter identities, user grants, central Firestore access policy, durable security audit, Fleet records or Fleet reset state.
- Do not cache sensitive project data in persistent browser storage. The website login session and navigation preferences are managed independently.
- For a shared demo, enable a visible dataset version; concurrent users can change synthetic metrics while another session is open. The UI must indicate refreshed/stale data rather than falsely claiming an immutable snapshot.

---

## 24. Non-functional requirements

### 24.1 Performance

Targets for the demo environment:

- initial dashboard visible within 3 seconds under normal hosted conditions;
- common filtered analytical queries within 2 seconds;
- ordinary CRUD actions within 1 second excluding network latency;
- progress feedback for AI operations exceeding 2 seconds;
- timeout and fallback handling for external AI calls;
- pagination or virtualisation for large employee and candidate tables.

### 24.2 Accessibility

Aim for WCAG 2.2 AA practices:

- keyboard navigation;
- labelled controls;
- visible focus;
- sufficient contrast;
- non-colour status indicators;
- chart summaries or accessible data views;
- meaningful error messages;
- responsive layout from mobile width upward.

### 24.3 Reliability

- transactional imports;
- validation before mutation;
- idempotency or duplicate protection for repeated AI/import requests;
- deterministic controlled demo scenarios;
- audit record for critical failures;
- retry only where safe;
- no silent data loss.

### 24.4 Portfolio integration and availability

- Use the existing Vercel frontend and Render backend without introducing a separate deploy target by default.
- Keep Workspace/Project assets and CSS scoped; preserve the host's Fleet, RAG, Resume, Contact, Telegram and public SEO behavior.
- A broken Workforce optional bootstrap must not prevent the FastAPI public host from starting.
- The Workforce route may be unavailable during Render sleep/cold start. Show a clear retry/loading message; do not equate a timeout with permission denial.
- The project catalogue and login should remain independent of waking Render where the existing host permits.
- An authenticated user's application must not assume persistent SQLite changes after restart; make a deterministic reseed and status check available.

### 24.5 Observability

Record:

- correlation ID;
- endpoint;
- status;
- duration;
- AI token/cost metadata if available;
- model and prompt version;
- import batch status;
- validation failures;
- forecast-run status.

Do not log secrets or unnecessary free-text personal data.

---

## 25. Error and edge-case handling

The specification must be implemented for:

- AI API unavailable;
- AI timeout;
- malformed AI JSON;
- hallucinated response ID;
- empty survey;
- insufficient responses;
- comments without analysable content;
- token-limit overflow;
- duplicate analysis request;
- partially completed AI analysis;
- failed import transaction;
- invalid Excel schema;
- reset of the dedicated Workforce SQLite data (not Firestore or Fleet);
- stale browser state after reset;
- simultaneous updates and a reset/import race;
- unknown reference codes;
- empty forecast series;
- too few historical periods;
- zero denominator in KPI;
- suppressed small group;
- deleted or superseded reference value.

Never display `NaN`, `Infinity`, unexplained blanks or a false zero. Show `Not available`, `Suppressed`, `Insufficient data` or a specific validation message.

---

## 26. Interview demonstration modes

### 26.1 90-second scenario

1. Open Recruitment Overview.
2. Show vacancy gap and time to hire.
3. Amend one candidate or contract event.
4. Show a KPI refresh.
5. Ask Insight Pilot one controlled question.

### 26.2 Five-minute scenario

Add:

1. recruitment funnel;
2. candidate feedback report;
3. AI-identified signal with evidence IDs;
4. forecast toggle;
5. metric tooltip;
6. architecture overview.

### 26.3 Ten-minute scenario

Add:

1. Excel validation preview;
2. scenario planning;
3. analyst review and publication;
4. management action;
5. BPMN;
6. audit history;
7. data-quality page.

### 26.4 Guided mode

Provide a **Run interview scenario** control that applies the intended dates and filters and navigates through a stable sequence. It must not hide the normal interactive functionality.

---

## 27. Acceptance criteria

### 27.1 End-to-end data change

- An authorized Workforce Member changes contracted FTE or a recruitment event.
- The change persists in **Workforce-owned SQLite** and not in Fleet or Firestore.
- History and project-local audit event are created.
- Affected Gold metric changes after refresh/recalculation.
- The dashboard tooltip shows the updated components, period and data version.
- A read-only global site visitor without a Workforce grant cannot access the underlying API.

### 27.2 Excel import

- Valid workbook produces a preview.
- Invalid rows are identified precisely.
- No database mutation occurs before confirmation.
- Confirmed import is transactional within the Workforce database.
- Audit and impact summary are created.
- Repeated confirmed import is idempotent; stale preview after reset is rejected.

### 27.3 Recruitment funnel and vacancy reconciliation

- Vacancy lifecycle metrics count vacancies/positions; application funnel metrics count eligible distinct applications.
- Stage counts reconcile to source application events without duplicate inflation.
- Conversion denominators and cohort windows are explicit and consistent.
- Candidate start is distinct from accepted offer, and application-to-start conversion uses application grain.
- Filters preserve reconciliation.
- Closing a vacancy as `Cancelled` without a starter does not fabricate filled WTE or lower the workforce gap.
- Filling a vacancy through an actual valid starter updates the relevant establishment/filled-WTE metrics.

### 27.4 Temporal history

- Updating assignment or contract does not destroy prior history.
- Point-in-time queries return the correct historical state.
- Current-state query returns one applicable current record per entity, subject to explicit business exceptions.

### 27.5 AI analysis

- Source comments are synthetic and identified by response ID.
- PII/redaction step runs before external submission.
- AI response validates against schema.
- Unknown response IDs cause rejection.
- Signal counts reconcile to unique response IDs.
- AI output enters `Awaiting analyst review`.
- Unreviewed findings do not appear as published Gold facts.
- A Workforce Member can explicitly confirm, amend or reject while recording the reviewer's Firebase UID and rationale.
- Review history is retained until the permitted Workforce demo reset.

### 27.6 Survey weighting and segment signals

- The system calculates representation weights only when approved population totals exist.
- Weighting variables, source totals, formula, trimming range and run version are recorded.
- Default weights are trimmed to `0.5–2.0`, unless a documented configuration specifies otherwise.
- Weighted and unweighted results are both available.
- Effective sample size is displayed for weighted results.
- Seniority, pay band, tenure, promotion or qualification do not automatically make an individual opinion more valuable.
- Segment prevalence, organisation-wide prevalence, percentage-point difference and prevalence ratio reconcile to source responses.
- Suppression rules apply before segment results leave the API.
- Review Priority components and formula are visible and reproducible.
- Review Priority is not presented as a probability or used for automatic employment decisions.
- Triangulated measures use association wording and do not claim causation.

### 27.7 Suppression

- API does not return prohibited small-group detail.
- UI displays a suppression explanation.
- Filter combinations cannot reconstruct an individual result.

### 27.8 Forecast

- Forecast toggle works.
- Actual and forecast periods are visually distinct.
- Method, horizon, assumptions and error/limitation are visible.
- Insufficient history prevents misleading output.

### 27.9 Insight Pilot

- Controlled query returns a calculation from approved backend logic.
- Answer shows filters and period.
- Metric definition is accessible.
- Survey claims cite response IDs.
- No unsupported causal claim is generated.

### 27.10 Demo resilience

- Prebuilt reviewed report works without AI API.
- Controlled data seed reproduces the intended scenario.
- Workforce reset restores a known state and increments dataset generation.
- A reset cannot modify Fleet SQLite or any central Firebase/Firestore identity, grant or security-audit record.
- UI discloses that Workforce data may reset periodically.
- A session opened before reset refreshes stale data rather than silently rendering obsolete metrics.

### 27.11 Route, identity and project isolation

- `/portfolio` shows the authorized portfolio catalogue without exposing unauthorized project contents.
- `/portfolio/workforce-intelligence` serves one SPA-like Next.js application with working internal navigation, reload and deep-link behavior.
- Unauthenticated direct browser/deep-link/API requests are denied.
- A valid Firebase session for a UID without a Workforce grant is denied, even if the UID is admitted to Portfolio Lab or granted access to Fleet.
- Owner-provisioned email/password identity with an explicit Workforce grant can access the complete project without Workforce role selection.
- Every protected FastAPI route independently rejects unsigned/expired credentials, revoked grants and direct-Render bypass attempts.
- No project-specific auth table, Fleet import, shared SQLite or old Fleet password bypass exists.
- Host Fleet and public site regressions remain green.

### 27.12 SPA visual and usability acceptance

- UI layout is Fleet-inspired but brand-original; shared theme tokens or standalone primitives do not depend on Fleet internals.
- Four modes and their internal navigation work without unnecessary document reloads.
- Dark/light theme, loading/empty/error/suppression states, readable tooltips and key keyboard paths work.
- Desktop interview demonstration meets stated response targets under tested conditions; mobile/tablet layouts remain usable.

---

## 28. Testing strategy

### 28.1 Unit tests

- canonical metric formulas and zero denominators;
- vacancy lifecycle versus application funnel grains and cancellation/fill edge cases;
- stage transitions, duplicates, cohort eligibility and timing;
- effective-date and non-overlapping version logic;
- suppression rules and filter inference limits;
- representation-weight calculations and trimming;
- effective-sample-size calculation;
- segment prevalence and prevalence-ratio calculations;
- Signal Review Priority calculation and versioning;
- Pydantic models and frontend contract/type checks;
- AI evidence validation and survey counting;
- data-quality rules;
- forecast input validation and insufficient-history behavior;
- dataset generation, optimistic-update checks and reset confirmation policy.

### 28.2 Integration tests

- Firebase signed session and project membership to FastAPI grant enforcement;
- direct Render origin denies requests without a Workforce grant;
- identity admission alone never allows project data access;
- Excel upload to Workforce transaction and project-local audit;
- operational update to Gold-view refresh;
- cancelled versus filled vacancy reconciliation;
- survey generation to redacted AI request;
- AI output to review workflow and Gold publication;
- authorized member can reset only Workforce demo data;
- Firestore platform records and Fleet SQLite remain untouched by Workforce reset;
- optional Workforce bootstrap failure does not fail public backend startup;
- Next.js authenticated BFF forwards only to configured Render origin and does not expose signed cookies to browser JS.

### 28.3 End-to-end tests

- Owner-provisioned email/password login → Workforce project grant → catalogue → protected SPA;
- denied access to Workforce for a platform-admitted user with no Workforce grant;
- create vacancy → applicant → accepted offer → starter → adjusted KPI;
- cancel vacancy without starter → no fabricated establishment improvement;
- change employee FTE and inspect historical WTE;
- mark leaver without deleting employee;
- validate/commit Excel workbook and inspect impacts;
- generate synthetic concern survey → AI response → analyst review → published finding → management action;
- reset demo dataset and reload a previously open SPA session;
- smoke Fleet, Resume, public Chat/RAG, Contact and relevant redirects after integration.

### 28.4 AI evaluation set

Maintain 50–100 manually labelled synthetic comments with expected:

- theme;
- classification;
- severity;
- evidence span;
- response ID.

Track:

- structured-output validity;
- theme precision/recall/F1;
- unclassified rate;
- analyst amendment rate;
- unsupported-evidence rate;
- invented-response-ID rate.

Hard requirements:

- invented response IDs: 0% in accepted/published findings;
- unsupported evidence in published reports: 0%;
- valid structured output after connector validation: target at least 99% through bounded retry/repair or controlled failure;
- all published findings reviewed through an explicit human action in the demonstration workflow.

### 28.5 CI and delivery gates

- Run existing `task ci` and all configured host CI jobs; do not remove or weaken Fleet/RAG/public-site tests.
- Extend project registry and import/CSS boundary checks to recognize `workforce_intelligence`, without introducing a speculative plugin framework.
- Run Firebase-authenticated and unauthorized negative-path tests in an isolated test environment/emulators; real email/password smoke is needed before inviting visitors.
- Confirm the release switch is disabled before project membership checks are proven; after enablement, verify direct Render denial for a valid identity without a Workforce grant.
- Document tested commit, preview URL, dataset seed, known caveats, and production smoke results. A passing isolated unit suite is not evidence of production availability.

---

## 29. Implementation priorities and phased delivery

This project should be built in **vertical slices** with genuine persistence and governed metrics, not as disconnected mock screens. Full scope remains the target, but a reliable interview sequence is the first release goal.

### Prerequisite P0: platform integration gate

- Reinspect current `main` and the canonical Portfolio Lab identity/access TRS and ADR.
- Confirm the current `/portfolio` route does or does not exist; implement only the catalogue integration required here.
- Register the project in `portfolio/catalog/registry.json` with a project-owned `project.json` manifest and a default-private/disabled catalogue entry until access is enforced.
- Use the host's Firebase email/password login, session, and platform admission.
- Implement/reuse **shared project-grant verification**, mapping any granted Workforce participant to one effective `Member` capability. If not ready, allow only a restricted Owner preview.
- Prove direct Render and Vercel BFF authorization before publishing Workforce data.
- Ensure no new project grants are inferred from existing Fleet grants or from general Lab admission.

### Interview MVP — first deliverable

Required end-to-end vertical slice:

1. Protected entry via `/portfolio/workforce-intelligence` and same-origin BFF to FastAPI.
2. SPA shell with four visible modes and working navigation; unfinished full-scope pages visibly identified as planned rather than presented as functional.
3. Dedicated Workforce SQLite migration, deterministic seed, `dataset_generation`, project-local audit, reset.
4. Selected realistic synthetic workforce/vacancy/application data and a documented metric catalogue.
5. Executive Recruitment Overview with open vacancies, vacancy WTE/gap, new starters, median time to hire, offer acceptance and a correct application-grain funnel.
6. One persisted contract/FTE or recruitment mutation visibly changes a governed KPI.
7. Separate filled-versus-cancelled vacancy behavior shown correctly.
8. One prebuilt, reviewed People Voice survey report with valid evidence IDs and an approved Gold signal; works without external AI.
9. At least one controlled Insight Pilot analytical intent using the backend's canonical metric definition (optional LLM narrative, deterministic data calculation).
10. Architecture Overview showing operational → Bronze → Silver → Gold, owned datasets and published lineage.
11. Stable 90-second and five-minute guided interview sequences, explicit synthetic disclaimers and AI fallback.
12. Required security/isolation tests and host regressions passing before any non-Owner rollout.

The MVP may expose additional pages or placeholders only if clearly labeled as non-operational. It must not claim that full-Scope Excel import, forecasts, survey generation or every KPI exists before it does.

### Full PoC Phase 1: operational completeness

- Complete employee, contract, assignment, vacancy, candidate, offer, checks, starter, learning/PDR and leaver CRUD.
- Complete effective-dated history, integrity checks, standardized event states and audit.
- Controlled 4,400-record synthetic dataset, 36-month history and documented location/role inventories.
- Excel template, validation preview, transactional import/export and controlled reset.
- Source and assumption register.

### Full PoC Phase 2: analytical core

- Complete Bronze/Silver/Gold transformations and reconciliation.
- Executive and secondary analytical dashboards, full vacancy lifecycle and application funnel.
- Recruitment source, retention, development, WTE, cohort, inclusive recruitment, and data quality views.
- Canonical metric catalogue, drill-through and explanatory tooltips.

### Full PoC Phase 3: People Voice and AI

- Survey builder, response generator, controlled taxonomy.
- Representativeness, weighting, effective sample size, segment analysis, Signal Review Priority and triangulation.
- Existing external AI connector via approved server adapter; output schema validation and evidence integrity.
- Human review workflow, three demonstration reports and action linkage.

### Full PoC Phase 4: forecasting and architecture

- Forecast toggle and transparent model/baseline comparison.
- Scenario planning and management actions.
- Bronze/Silver/Gold viewer, data model, lineage, BPMN and guided interview mode.

### Full PoC Phase 5: hardening and release

- Accessibility and responsive review.
- Performance and cold-start observations; indexing/query tuning.
- Failure/fallback, concurrency, repeated import, reset and BFF negative-path testing.
- CI, production smoke, source citations and disclaimers.

### Engineering sequencing principles

- Prefer small domain-owned services and explicit ports/adapters over a universal CRUD framework.
- Centralize cross-cutting identity/grant contracts in the shared platform and metric logic inside Workforce; do not duplicate either.
- Create migrations incrementally with delivered features. Avoid generating all full-scope tables before their meaning and invariants are tested.
- Preserve the existing website's architecture gates and deployment footprint.

---

## 30. Definition of done

### 30.1 Interview MVP done

The MVP is complete only when:

- `/portfolio` exposes the correct registered project entry to eligible visitors, with no ungranted data disclosure;
- `/portfolio/workforce-intelligence` loads as a protected SPA-style application in existing Next.js;
- email/password authentication and an explicit Workforce project grant are enforced by Next.js **and** direct FastAPI origin;
- a project member has one uniform project permission set and can run the demonstrated workflows;
- dedicated Workforce SQLite, seed, reset and project-local audit work independently of Fleet and Firestore;
- a persisted vacancy/candidate/FTE action produces a correct, visible KPI change;
- application funnel counts do not mix vacancy and application grains;
- cancelled vacancy behavior is not misreported as a filled establishment gap;
- canonical metric tooltips, at least one pre-reviewed survey report and stable AI fallback work;
- a documented 90-second and five-minute interview flow succeeds;
- host regressions, authorization negative paths and direct Render checks pass;
- all visible features that are unfinished are labeled as planned, not represented as operational.

### 30.2 Full PoC done

The full PoC is complete when:

- the application is deployed in the existing website;
- Workforce Intelligence opens by default;
- four primary modes work against one **Workforce-owned** persisted data model;
- the synthetic dataset is reproducible;
- the first 15 fictional featured names appear as configured;
- workforce and recruitment changes affect dashboards;
- Excel validation/import/export works;
- material metrics have governed definitions and tooltips;
- separate vacancy and application lifecycle metrics reconcile;
- workforce outcomes reconcile to establishment and dated source events;
- People Voice generates controlled synthetic responses;
- response rates, representativeness and weighting limitations are visible;
- weighted and unweighted survey results can be compared;
- segment signals and governed review priority can be reproduced;
- one report is prebuilt and reviewed;
- two reports can be generated and analysed during demonstration;
- AI findings cite valid evidence IDs and explicit member-initiated review precedes Gold publication;
- forecasting is transparent and limited to recruitment/workforce data;
- Bronze/Silver/Gold, lineage, quality and BPMN are visible;
- light and dark themes work;
- the demo can be reset to a stable state without touching Fleet or Firestore access control;
- all screens clearly identify the product/data as unofficial and synthetic;
- central user identities/grants remain durable after any Workforce database loss;
- there is no project-specific role hierarchy, separate credential store, or new paid infrastructure by default.

---

## 31. Final product statement

The product should be presented as:

> **A governed Workforce & Recruitment Intelligence proof of concept that demonstrates how synthetic people data can be captured, validated, modelled, analysed, forecast and converted into reviewable management actions, with responsible AI used to identify evidence-backed signals rather than make autonomous workforce decisions.**

---

## Appendix A. Public-source anchors

The following public SCAS material informs the functional emphasis of this specification:

1. **SCAS People Strategy 2023–2026** identifies vacancy rates, applicant numbers, course fill, time to recruit, offer acceptance and attrition as recruitment measures. It also identifies PDR compliance, career progression, learning and development, Staff Survey, People Voice, inclusive appointments and people-data availability as measures or priorities.
2. **SCAS Annual Report and Accounts 2025/26** reports workforce establishment, WTE, starters, turnover, retention, sickness, vacancy and recruitment activity by major service line. These values may inform organisational scale and synthetic scenario design but must not be represented as results calculated from synthetic employee records.
3. **SCAS Workforce Race Equality Standard reporting** provides a public contextual benchmark for recruitment equality. Any such benchmark must retain its source period and definition and must remain separate from synthetic calculated outcomes.

Suggested source register entries:

- https://www.scas.nhs.uk/wp-content/uploads/2023/05/SCAS-People-Strategy-2023-2026-web.pdf
- https://www.scas.nhs.uk/wp-content/uploads/2026/09/SCAS_Annual_Report_and_Accounts_2025-26.pdf
- https://www.scas.nhs.uk/wp-content/uploads/2026/10/WRES-Annual-Report-2026a.pdf
- https://www.scas.nhs.uk/about-scas/performance/

---

## Appendix B. Repository implementation blueprint

This appendix prescribes **ownership and integration boundaries**, not a claim that the files already exist. Implementation can refine file names while preserving the contracts.

### B.1 Target tree

```text
repo/
├── portfolio/
│   ├── catalog/
│   │   └── registry.json                 # add workforce_intelligence
│   ├── fleet_hub/                        # existing, preserve unchanged
│   └── workforce_intelligence/
│       ├── project.json                 # stable ID, route, API prefix, catalogue metadata
│       ├── README.md                    # local setup, seed, tests and deployment notes
│       ├── docs/
│       │   ├── README.md                    # links to the canonical specification
│       │   ├── architecture.md
│       │   ├── data-dictionary.md
│       │   ├── metric-catalogue.md
│       │   └── interview-runbook.md
│       ├── frontend/
│       │   └── src/
│       │       ├── index.ts             # public frontend entry point
│       │       ├── app/                 # SPA shell, mode navigation
│       │       ├── features/            # workforce, recruitment, voice, architecture
│       │       ├── components/          # project-scoped reusable UI primitives
│       │       ├── api/                 # typed BFF client; no Firebase Admin SDK
│       │       └── styles/              # scoped CSS/theme tokens
│       └── backend/
│           ├── pyproject.toml           # if required by host packaging conventions
│           ├── src/workforce_intelligence/
│           │   ├── router.py            # public FastAPI router entry point
│           │   ├── bootstrap.py         # optional/lazy project database initializer
│           │   ├── api/                 # thin Pydantic HTTP handlers
│           │   ├── domain/              # entities, invariants, calculations
│           │   ├── application/         # use cases/orchestration/commands
│           │   ├── persistence/         # SQLite adapter, migrations, repositories
│           │   ├── analytics/           # Bronze/Silver/Gold projections, metrics
│           │   ├── surveys/             # generation, taxonomy, review
│           │   ├── ai/                  # provider adapter and output validation
│           │   ├── forecasting/
│           │   └── fixtures/            # deterministic synthetic seeds
│           └── tests/
├── frontend/
│   └── app/
│       └── portfolio/
│           ├── page.tsx                 # host-owned project catalogue adapter
│           └── workforce-intelligence/
│               ├── page.tsx             # host-owned protected route adapter
│               └── api/                 # same-origin authenticated BFF adapter
├── backend/app/main.py                  # registers public Workforce router
├── docs/specifications/portfolio-lab-auth-access.md  # shared authority
└── Taskfile.yml / .github/workflows/ci.yml
```

**Important:** The existing repo may use different entry-point/package conventions; reuse them rather than mechanically introducing a separate package format. Do not move `fleet_hub` or its existing public route as part of Workforce implementation.

### B.2 Example project manifest (illustrative, confirm actual schema)

```json
{
  "schemaVersion": 1,
  "id": "workforce_intelligence",
  "slug": "workforce-intelligence",
  "title": "Workforce & Recruitment Intelligence",
  "summary": "Synthetic recruitment and workforce analytics demonstration.",
  "category": "Data & Analytics",
  "technologies": ["Next.js", "React", "TypeScript", "FastAPI", "Python", "SQLite", "Firebase Auth"],
  "mode": "embedded",
  "demo": {
    "path": "/portfolio/workforce-intelligence",
    "apiPrefix": "/api/workforce"
  },
  "catalog": { "visible": false, "featured": false }
}
```

The metadata should first remain invisible/private until the route authorization is production-tested. Publication must not create grants automatically. The host registry lists project IDs, while the per-project manifest defines its metadata; do not copy the catalogue into Firestore as a competing canonical source.

### B.3 Import and dependency rules

1. The website host imports only the Workforce public frontend and backend entries.
2. Workforce packages may consume explicit platform contracts/dependencies supplied by the host, but never import website-private implementation modules.
3. Workforce must not import `fleet_hub` backend services, frontend components, CSS modules or database connections.
4. Any reusable visual primitive should be placed in a **neutral** shared UI module only if actual reuse is justified; both apps may depend on it, but neither should own the other's UI.
5. Route adapters handle auth, transport and composition; domain behavior remains in Workforce application/domain layers.
6. All environment values and API prefixes must be scoped/namespaced; preserve host-wide `/api/*` behavior and public streaming.
7. Extend architecture import checks, TS aliases, Vercel build inclusion, Docker package installation, and test selectors as required by current main.
8. Keep package versions compatible with existing locked frontend/backend dependencies; do not create a second uncontrolled React or FastAPI environment.

### B.4 Suggested operation-to-domain dependency direction

```text
host route adapter → project public entry
project HTTP route → auth dependency (shared platform interface)
                   → project application service
                   → project domain contracts and rules
                   → project-owned repository/analytics interface
                   → SQLite adapter / AI provider adapter
```

No backend project handler should reach into another project's data and no raw browser request may call a privileged Firebase Admin SDK. Domain logic remains independently unit-testable without running a website or OAuth emulator.

---

## Appendix C. Worked semantic examples and decision tables

### C.1 Vacancy state versus WTE impact

| Event | Vacancy status | Starter recorded? | Vacancy pipeline count | Filled substantive WTE / gap effect |
|---|---|---:|---|---|
| Approved opening | Open | No | Open vacancy increases | No filled-WTE gain |
| Advertised | Open/Advertised | No | Recruitment active | No filled-WTE gain |
| Cancelled without fill | Cancelled | No | Open requisition count decreases | No new substantive WTE; gap does not improve solely because status closed |
| Candidate accepted offer | Open / offer accepted | No | Offer-stage progress | No actual starter WTE yet |
| Candidate actually starts | Filled or partially filled | Yes | Application enters Started, position fill recorded | Substantive WTE updates according to effective contract/assignment and vacancy fill |
| Establishment reduced | Closed/Canceled as applicable | No | May reduce open vacancy count | Budgeted establishment WTE changes, with explicit effective-dated approval; formula recalculated |

The exact effect of establishment changes, substantive/temporary positions and partial fills depends on source flags and canonical definitions. Never force two different metrics to coincide by manipulating a vacancy status.

### C.2 API policy table

| Request | Firebase identity | Project grant | Result |
|---|---|---|---|
| Public host `/api/chat` | Not required by this project | Not required | Unchanged public behavior |
| `/portfolio` catalogue | Depends on host design | Needed to show specific private project entry | Do not reveal restricted content |
| Workforce page | Required | Required | Authorized SPA entry |
| Workforce `GET` | Required | Required | Authorized synthetic data only |
| Workforce `POST/PATCH` | Required | Required | Domain validation + audit + mutation safeguards |
| Workforce AI request | Required | Required | Rate limit + approved connector + no secrets exposed |
| Workforce reset | Required | Required | Explicit confirmation + mutex + scoped reset + audit |
| Firebase user provisioning | Platform Owner | Platform policy | Never a Workforce domain endpoint |
| Fleet API | Existing Fleet security policy | Fleet grant after its migration | No Workforce permissions implied |

### C.3 Synthetic recruitment scenario example

Use controlled, illustrative cohort data, not public SCAS results:

- 10 vacancies approved and advertised;
- 250 applications received and validated for the chosen cohort;
- 40 candidates interviewed;
- 15 accepted offers;
- 12 candidates actually started.

Then:

- `applications per vacancy = 250 / 10 = 25`;
- `application-to-start conversion = 12 / 250 × 100 = 4.8%`, if all 12 starts are attributable to the same sufficiently observed application cohort;
- accepted offer is not a starter, and vacancy-to-application *conversion* must not be displayed as a percentage;
- a cancellation changes requisition status but does not manufacture a start.

### C.4 AI review state example

```text
Synthetic survey responses
 → redact and assign response IDs
 → AI proposes a draft signal (not Gold)
 → JSON + allowed response IDs verified
 → human Member reviews evidence and explicitly confirms/amends/rejects
 → only confirmed/amended result published to Gold
 → optional management action created
```

A project Member may be both the person requesting AI analysis and the person performing the explicit review. This PoC demonstrates a governance workflow rather than separation of duties appropriate to real production HR systems; do not claim it is equivalent to a real independent reviewer control.

---

## Appendix D. Security and integration regression matrix

All tests must use synthetic data and isolated credentials. The exact CI file/test names may be adjusted to current repository conventions.

| ID | Scenario | Expected result | Release gate |
|---|---|---|---|
| AUTH-01 | Missing Firebase session on protected browser route | Login redirect/no data | MVP |
| AUTH-02 | Valid Firebase session without Workforce grant | 403 or safe access-denied; no protected payload | MVP |
| AUTH-03 | Valid Fleet grant only | No Workforce access | MVP |
| AUTH-04 | Valid Workforce grant, email/password | Complete application Member actions | MVP |
| AUTH-05 | Expired/revoked Firebase session | Denied at both Vercel and direct Render | MVP |
| AUTH-06 | Direct Render call with no credential | 401, no data | MVP |
| AUTH-07 | Direct Render with signed identity but no project grant | 403, no data | MVP |
| AUTH-08 | Firestore grant service unavailable | Fail closed, controlled temporary error | MVP |
| AUTH-09 | Forged email, UID or role header | Ignored; authorization denied | MVP |
| AUTH-10 | Browser-supplied backend URL | BFF refuses to forward signed session | MVP |
| DATA-01 | Change FTE with effective date | Relevant Gold metric recalculated, history preserved | MVP |
| DATA-02 | Cancel unfilled vacancy | No false starter or filled WTE | MVP |
| DATA-03 | Fill approved vacancy with actual starter | Correct event/fill metrics | MVP |
| DATA-04 | Reset Workforce while Fleet exists | Workforce resets; Fleet DB unchanged | MVP |
| DATA-05 | Reset Workforce while Firestore grants exist | All central grants/identities unchanged | MVP |
| DATA-06 | Open old SPA tab after reset | Dataset version mismatch triggers refresh | MVP |
| DATA-07 | Concurrent import/reset | Serialized or conflict returned; no partial write | Full PoC |
| DATA-08 | Repeat confirmed import | No duplicate records | Full PoC |
| AI-01 | Unknown evidence response ID | Analysis rejected before publication | Full PoC |
| AI-02 | AI service unavailable | Pre-reviewed report and fallback still work | MVP |
| AI-03 | Unreviewed AI finding | Excluded from published Gold | Full PoC |
| AI-04 | Reviewed confirmed finding | Published with evidence lineage/audit | Full PoC |
| UI-01 | Navigate four modes | SPA transition, correct route/filter state | MVP |
| UI-02 | Refresh deep link | Session/grant checked, correct screen restored | MVP |
| HOST-01 | Fleet VOR Hub regression smoke | Existing route and API unchanged | MVP |
| HOST-02 | Public RAG/Chat/Contact smoke | Existing public behavior unchanged | MVP |
| HOST-03 | Workforce optional bootstrap fails | Host health and unrelated public routes survive | MVP |

---

## Appendix E. Implementation assumptions requiring explicit verification

These checks are implementation-time validation steps, **not unresolved product-design questions**:

1. **Current main:** confirm which shared Portfolio Lab RBAC/Owner UI stages have merged after the 14 November 2026 identity checkpoint. Do not assume future PRs exist.
2. **Catalogue:** confirm whether `/portfolio` route and access-controlled listing have been added; implement as part of project integration if still absent.
3. **Host package integration:** inspect exact public-entry import conventions and Docker/Vercel packaging before creating files; directory layout in Appendix B is a target pattern.
4. **Session transport:** confirm cross-host signed Firebase session BFF and its tests still match the active SDK and deployed security settings.
5. **Storage path:** choose and document the Workforce SQLite path, readiness/atomic seed process and migration lifecycle; avoid using Fleet's database path.
6. **Service capacity:** benchmark the 4,400-employee / 36-month dataset and AI requests on the existing free-tier environment; do not assume performance targets without measurements.
7. **Design tokens:** inspect Fleet's current style and extract stable visual concepts only where useful, without CSS/project-code coupling.
8. **Source inventory:** verify SCAS public documents, dates and organizational-scale references when preparing the actual seed; treat all unverified structure as synthetic.
9. **Production access:** keep the private project inaccessible until email/password account, grant, direct Render and BFF smoke checks succeed.
10. **QA:** distinguish tests proven in CI from tests proven against hosted Preview/production; both are necessary for release claims.

---

## Appendix F. Mandatory wording

### Global banner

> **Demo v1.0 | Prepared for an SCAS interview | Synthetic data only | Not an official SCAS system**

### Demo reset notice

> **Demo environment. Changes may be reset periodically.**

### AI notice

> **AI-identified signals require analyst review before operational or workforce decisions are made.**

### Signal wording

> **AI analysis identified a strong signal of [theme]. Analyst review is recommended.**

### Forecast notice

> **Illustrative forecast based on synthetic data and stated assumptions. It must not be interpreted as a forecast of actual SCAS performance.**

### Association notice

> **Observed relationships are analytical associations and do not establish causation.**
