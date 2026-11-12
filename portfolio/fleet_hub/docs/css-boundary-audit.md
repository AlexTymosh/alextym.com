# PR 4 — Website vs Fleet frontend boundary audit

Reviewed against `main` commit `dd7b7b730e4be4c9d056398b4b69ba5e72784575` (PR #214 merged on 2026-11-01).

## Findings

- The website owns `frontend/app/layout.tsx`, site navigation, footer, root metadata and the global stylesheet `frontend/app/globals.css`. Its base `html`, `body`, button and input rules are intentionally inherited as part of the existing *single-host* deployment.
- Fleet's current React components import only project-local `.module.css` styles and their own assets; the current CSS Modules do not use `:global` or `@import` escapes. Styles remain scoped to their CSS Module classes.
- The plain stylesheets `src/issue-hub-redesign.css` and `src/operations/workflow-redesign.css` are historical mockup overrides. They are not imported by current Fleet React modules or by project CSS Modules, so PR 4 removes them. The active redesign rules are already in project-owned `.module.css` files. This is dead-file removal, **not** a restyling exercise.
- The Fleet application uses fixed-position project-local CSS for its own full-screen workspace and login, while the website host continues to mount navigation/footer. Moving these routes into Next.js route groups would change layout lifecycle without a demonstrated isolation need, so PR 4 deliberately leaves the route tree and root layout in place.
- Existing Fleet stylesheet files contain historical `!important` override layers and large/minified selectors; their cleanup is a **separate visual refactor**, requiring screenshot comparison and authenticated workflows. It is not safe to reformat or consolidate these rules in a boundary-only PR.

## Enforced contracts

`node scripts/check-website-portfolio-boundaries.mjs` (part of `task portfolio:check` and `task ci`):

1. Fleet project source can import other Fleet files, React and Next.js only. Relative imports cannot escape the module source root; unexpected bare dependencies are rejected.
2. Fleet stylesheets must be `.module.css`; `:global` escapes, document-global selectors and CSS `@import` are forbidden.
3. The Next.js host can import Fleet through the **single public `@fleet-hub` entry** only in `/fleet-vor-hub/page.tsx`.
4. The established website shell and all three Fleet redirect adapters must remain intact; the Fleet page stays `noindex`/`nofollow` and the hidden portfolio catalogue stays unpublished.
5. Browser E2E checks that the demo is `noindex` and website navigation remains available after returning to the home page.

## Accepted limitations

- Because there is one root Next.js layout, browser-element resets and theme primitives from `frontend/app/globals.css` are shared. This is *not* full CSS isolation. Fleet component selectors remain scoped by CSS Modules, and browser regression checks protect the current appearance. Stronger layout isolation would require an explicitly approved design change and before/after visual comparison.
- Import checking is a fail-closed static safeguard for current TypeScript imports; it is not a general JavaScript parser or a security sandbox. External dependencies must be reviewed and explicitly added to the allowlist when genuinely required.
- Browser tests rely on the existing Playwright suite and mocking of `/api/vor/session`; authenticated workflow E2E belongs to PR 5.

## Local validation

```powershell
node scripts/check-website-portfolio-boundaries.mjs
task ci
task docker:build
```

Check the Fleet login page and the Home/Resume/Chat/Contact routes visually on desktop and mobile before merging. No API, SQLite, runtime database, Docker, Render or Vercel configuration changes are made in this PR.
