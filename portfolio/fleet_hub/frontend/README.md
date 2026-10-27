# Fleet Hub frontend (planned destination)

This directory is intentionally documentation-only in PR 1.

In the dedicated frontend migration PR, move **application implementation** from `frontend/app/fleet-vor-hub/` into `portfolio/fleet_hub/frontend/src/`. Keep the Next.js filesystem routes in `frontend/app/fleet-vor-hub/` as thin host adapters, with no domain logic.

Preserve the public `/fleet-vor-hub` URL, three existing redirect routes, authentication behavior, API calls, CSS Modules and bundled image assets. Audit global CSS selectors before moving them; prevent project CSS from styling website pages.

The host's Next.js + Vercel setup must explicitly include source code outside the existing `frontend/` root. Decide the minimal local package/workspace wiring in that implementation PR; do not add it prematurely.
