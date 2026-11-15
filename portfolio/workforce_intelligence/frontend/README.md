# Workforce frontend

`src/index.ts` is the public entry imported by the protected Next.js page via
`@workforce-intelligence`. The SPA calls the same-origin Workforce BFF through
`data-api.ts`. The executive overview and directory use the live SQLite-backed
contracts. The authenticated Playwright smoke checks the browser DTOs against
the actual FastAPI responses and exercises an effective-dated FTE update.

The local offline preview keeps its own route and makes zero API requests.
Project styles are scoped with CSS Modules. No Fleet components are imported.
