# Frontend

Public entry: `src/index.ts`. The host owns the route adapter and session check; this project owns its visual content and CSS Modules. The foundation is server-rendered, uses the existing React runtime, and has no client network, media, storage or global document mutations. Future room shell and lazy activity components belong here. Use localized dictionaries, not hardcoded text in components. No imports from other portfolio projects or site internals.

`rooms/RoomCore.tsx` owns the room administration screens, `rooms/client.ts` the transport DTOs, `room-transport.ts` the exact allowed operations. The route-local host adapter supplies Firebase login and cookie forwarding. All labels use project-local Russian dictionaries; no global layout change.
