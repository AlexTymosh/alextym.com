# Architecture — SP01–SP05

Status: SP05 candidate; not activated. SP01–SP04 are merged. The Russian requirements remain the normative product specification.

## Composition and dependency direction

```mermaid
flowchart TD
  Next[Next.js host route] --> Shell[SamePlace public frontend entry]
  Next --> Lab[Host Lab session and project grant]
  FastAPI[FastAPI host composition root] --> Guard[Host SamePlace access adapter]
  FastAPI --> Router[SamePlace public router]
  Guard --> Lab
  Shell --> Locale[Project-local dictionaries]
  Router --> DTO[Read-only foundation response]
  Contracts[Activity manifest metadata contracts]
```

The host owns infrastructure and authentication; SamePlace owns application behavior. The original status router has no data access; the separate room router uses an injected transactional store. Pure activity contracts import Pydantic only; no host, Firebase or legacy dependency. Existing generic repository boundary checks and the project-specific guard enforce static ownership. These are preventive checks, not a sandbox. Future services must receive infrastructure via explicit ports and adapters. Do not add room, chat, game, asset or media logic to `backend/app` or `frontend/app`.

## Integration points

| Host path | Additive change |
|---|---|
| `portfolio/catalog/registry.json` | Register `sameplace` (catalog hidden) |
| `frontend/tsconfig.json`, route adapter | Public `@sameplace` import and guarded route |
| `backend/pyproject.toml`, `uv.lock`, `Dockerfile` | Editable package; existing FastAPI/Pydantic dependencies only |
| `backend/app/main.py`, security adapter | Mount `/api/sameplace` with fail-closed dependency |
| `Taskfile.yml`, CI | Include SamePlace source/test paths, freeze and localization checks |

## Access and runtime

`SAMEPLACE_ENABLED` is an exact `true` server-side flag, off by default. `PORTFOLIO_LAB_ENABLED` must also be true. Disabled requests return 404 before auth or provider calls; the original status endpoint requires the existing project grant. Room Core verifies identity separately and enforces per-room authorization; no global grant is created. Room writes are transactional and the browser uses a scoped BFF. No eager database initialization; SP03 adds the disabled-by-default project-owned WS transport. No change to global layout, identity rules, Firestore rules, legacy route, old data, cloud billing or deployment settings.

`GET /api/sameplace/status` returns `{"project_id":"sameplace","stage":"foundation","contract_version":1}` after authorization. It does not expose UID, tokens, provider settings, hidden game state or implementation secrets. This is not a health endpoint for unauthenticated clients.

## Future modules

Room Core is implemented for durable room administration. Social/Realtime is implemented in SP03; SP04 adds independent scene and music state. SP05 implements room-owned media; Activity Host and isolated engines remain planned. The activity manifest contract in `backend/src/sameplace/contracts/activity.py` is a first validated metadata seam. It distinguishes module, contract, state and rules versions, player counts, roles, spectator modes, UI entrypoint, supported locale tags and scene surfaces. The metadata can represent additional languages without enabling them; only the RU runtime dictionary is active. Publication must verify module support for every active locale. No code loading or entitlement runtime yet; add lifecycle ports in SP06 after Room Core is stable. A capability may only be published after its implementation and tests exist. Test-only fixtures are not available activities.

## Legacy freeze

Freeze source: `1e76eaa4c0ba58ceed0e5b5615917a6ee229f777` (PR42). `legacy-freeze.json` is generated from that immutable Git tree when applying this candidate. The guard re-reads the pinned tree, compares the manifest, index paths/modes/blob IDs, changed working-tree paths, hidden index flags and untracked protected paths. It includes all paths containing `preferans` outside `portfolio/sameplace/` (including tests, adapters and assets). Shared host files are protected by compatibility checks and review instead of blanket locking. A full repository tree is required to produce the exact inventory. CI fetches the pinned object because checkout can be shallow. No Git tag or branch protection is created automatically. Owner must protect the guard, manifest and CI configuration from ordinary unreviewed edits. An ignored cache is not a tracked file; on Windows, Git's symlink/filemode handling follows checkout/index semantics. Static checks do not prove runtime parity. Original tests and full repository CI are mandatory.

## Data and deployment

SP01 introduced no data. SP02 defines `sameplace_room_core_v1`; documents are created lazily by authorized commands only. No migration or production writes. Existing Firestore deny-all browser rule remains unchanged. Ephemeral presence lives in memory in SP03. Initial hosting uses existing Vercel/Render only and the strict GBP 0 policy. Keep the flag disabled even after merging; release is SP10, subject to actual capacity and quota evidence.

## SP02 layer composition

```mermaid
flowchart LR
  Browser[Room UI] --> BFF[Scoped host BFF]
  BFF --> API[Room HTTP adapter]
  API --> Auth[Injected verified identity]
  API --> Service[Room application service]
  Service --> Port[Transactional store port]
  Port --> Firestore[Injected Firestore adapter]
```

See [domain model](DOMAIN_MODEL.md), [security](SECURITY_AND_PERMISSIONS.md), [API](API_CONTRACT.md), and [ADR 0003](adr/0003-scoped-room-admission.md). All activity and social/media logic remains outside the room aggregate. No new third-party dependency or lockfile update is required: the host injects its existing Firebase client and transactional decorator.


## SP03 composition

```mermaid
flowchart TD
  Host[Existing FastAPI composition root] --> Public[SamePlace public router factory]
  Public --> Core[Room Core HTTP]
  Public --> Social[Social HTTP / WS]
  Core --> Policy[Shared room authorization and transactional command receipt]
  Social --> Policy
  Core --> Port[Injected transactional store]
  Social --> Port
  Core --> Invalidation[Post-commit observer]
  Invalidation --> Hub[Process-local Hub]
  Social --> Hub
  Browser[Room shell] --> BFF[Existing scoped BFF]
  BFF --> Core
  BFF --> Social
  Browser --> Socket[Direct authenticated socket]
  Socket --> Social
```

Room Core retains its storage and authorization ownership. The project factory in `social/composition.py` shares a bounded quota circuit and write limiter across both routers, without modifying host startup. `social/service.py` reuses public room transaction/authorization methods; `social/hub.py` has no storage, network or host imports. The BFF remains a thin origin/credential forwarding adapter. New UI components, layouts, translator keys and realtime client stay within SamePlace. See REALTIME_AND_MEDIA, RESOURCE_BUDGET, ADR 0004. SamePlace and realtime flags remain off by default.

## SP04 interior and music composition

`decor` owns catalogue, strict commands, transactional application service, and router. `social/composition.py` adds the router with existing host adapters, quota circuit, write limiter and hub; no website runtime changes. Frontend `decor` owns SceneCanvas, SceneEditor, MusicPlayer, typed projections and audio math. MeetingPanel mounts the persistent DecorPanel; it overlays the existing layout and does not own game rules. The browser uses existing BFF with exact added operation paths. Audio source lifetime depends on media source, not scene or skin. See INTERIOR_ENGINE and ADR 0005.

## SP05 room media boundary

MeetingPanel owns MediaProvider and local audio preferences. Existing room WS provides addressed signaling; MediaState shares the Hub lock and checks current room/channel membership, not game seats. The browser P2P provider owns peers, tracks, device selection and cleanup. Audio sinks stay above the visible scene; VideoTile is a replaceable presentation. No media frame is proxied, persisted or recorded. Future Activity SDK (SP06) mounts below the room lifecycle, and independent Preferans (SP07) must not remount the provider. ADR 0006 supersedes the previous order. Private pilot and actual capacity/rights evidence are conditional; public release remains SP10.
