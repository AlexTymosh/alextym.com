# Workforce frontend

`src/index.ts` is the only public entry imported by the Next.js host via the `@workforce-intelligence` TypeScript path alias. The present scaffold is deliberately not mounted while project grants are missing. All styling must remain scoped CSS Modules. No imports from `portfolio/fleet_hub` or host-private frontend code. Commit 03 replaces the scaffold with the SPA navigation and authenticated modes.
