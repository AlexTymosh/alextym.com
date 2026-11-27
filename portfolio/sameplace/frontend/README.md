# Frontend

Public entry: `src/index.ts`. The host owns the route adapter and session check; this project owns its visual content and CSS Modules. The foundation is server-rendered, uses the existing React runtime, and has no client network, media, storage or global document mutations. Future room shell and lazy activity components belong here. Use localized dictionaries, not hardcoded text in components. No imports from other portfolio projects or site internals.
