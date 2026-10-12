# SESSION_NOTES.md — Fleet VOR Hub, local demonstration

**Дата:** 12 October 2026  
**Branch:** `feat/fleet-vor-hub-demo`  
**Repository:** `AlexTymosh/alextym.com`  
**Status:** v3 local demo package. No changes pushed to GitHub/production by this package.

## 1. Цель

Показать руководству концепт **Fleet VOR Hub** — vehicle-centric workspace с единым Chatter,
историей внутренних сообщений, внешней переписки, событий KEY2 и HOTH, стадиями работы,
следующим действием, календарём MOT/Inspection/Service и dashboard. Цель — демонстрировать
возможность сократить ручную координацию между Outlook, Teams и fleet-системами.

**Это НЕ реальная интеграция KEY2/HOTH/Teams и НЕ действующая SCAS-система.** Все 20
автомобилей, регистрационные номера, гаражи, события, поставщики и статистика синтетические.

## 2. Пожелания владельца проекта

- Полностью переработать бизнес-логику; старый React-макет использовать только как дизайн-референс.
- Три колонки: отдельные визуальные карточки автомобилей слева; компактные details/workflow/next action
  в центре (без внутренней прокрутки при desktop-height); единый Chatter справа.
- Сценарии поломок отличаются: двигатель, MOT, покрышка, AdBlue, сервис и др.
- Даты MOT, Inspection, Service показываются в карточке авто и календаре с гаражами.
- Calendar содержит список автомобилей без забронированных плановых работ,
  если нужный тип обслуживания наступает в ближайшие 60 дней.
- Dashboard: KPI, VOR trend, доля Operational/VOR, причины и приоритеты.
- Защита страницы простым паролем, управляемым `VOR_DEMO_PASSWORD`.
- Сайт не должен добавлять маршрут `/fleet-vor-hub` в основную навигацию.
- Первые тесты отправки email проводятся только в simulated mode; live email включается явно,
  с allowlist, суточным лимитом 15 и настройками Resend.

## 3. Архитектура пакета и интеграция

Реально проверено по GitHub main 12.10.2026:

```
alextym.com/
  frontend/                         Next.js 16 / React 19
    app/fleet-vor-hub/
      page.tsx                      отдельная скрытая страница; noindex
      VorHub.tsx                    Vehicles + Chatter + Dashboard + Calendar
      vor.module.css                isolated SCAS-like theme; fullscreen overlay
  backend/                          FastAPI
    app/api/vor.py                  /api/vor; пароль / cookie / CRUD
    app/services/vor_store.py       sqlite3 storage, workflow and calendar operations
    app/services/vor_seed.sqlite3   20 vehicles / 40 tickets / synthetic events
    tests/test_vor_demo.py         API tests
    _local/vor_hub.sqlite3          создаётся ПРИ ПЕРВОМ ЗАПУСКЕ; Git-ignored
  scripts/
    install_vor_hub.py              idempotent main.py router registration
    start-vor-backend.ps1           local backend
    start-vor-frontend.ps1          local frontend
  SESSION_NOTES.md                  этот файл
  RUN_VOR_HUB.md                    Windows/PyCharm instructions
```

Next.js uses existing `/api/*` rewrite and `BACKEND_ORIGIN`. Router in `main.py` registered by
`scripts/install_vor_hub.py`. No extra npm or Python dependencies are required for v3 because
FastAPI/httpx already exist and SQLite is in Python stdlib. No changes to site navigation, home,
resume, RAG, contact or existing global CSS are required.

**Важно:** Page uses fixed full-screen interface over the existing root layout so it does not
inherit portfolio's max-width 1100px / global dark theme. For future production hardening,
prefer route-specific app shell instead of fullscreen overlay.

## 4. Реализованные локальные действия

- login/logout (HTTP-only signed cookie, 8h TTL; env password)
- GET bootstrap with 20 vehicles, tickets, all events, people, workflows, bookings, stats
- Internal Chatter message with vehicle/ticket link
- Email composer (simulated by default; live Resend optional, gated by whitelist and limit)
- Contact creation + per-vehicle subscriber management
- Workflow next-stage completion (synthetic log)
- MOT / Inspection / Service booking with garage and date
- Calendar month navigation + side list of due-but-unbooked items in 60 days
- Dashboard computed from the demo SQLite database

## 5. Essential env

Backend: `VOR_DEMO_ENABLED=true`, `VOR_DEMO_PASSWORD=Victoria` (can change),
`VOR_DEMO_SEND_REAL_EMAIL=false` (default).
Frontend: `BACKEND_ORIGIN=http://127.0.0.1:8000` for local work.

Do not commit actual env or send confidential business data to this demo.
See `RUN_VOR_HUB.md` for exact launch instructions and optional real-email config.

## 6. Current constraints / remaining work

1. Verify visually on user's Windows/Chrome at 1920x1080 and 1366x768. Full screen central pane
   is optimised for desktop; expanded steps panel may scroll by design.
2. Test end-to-end browser form interactions and CSS after installing npm dependencies in the
   user's existing repo (the packaging environment lacks network to install frontend modules).
3. Real inbound email threading not implemented. External email tab displays simulated/outbound events.
4. KEY2/HOTH records are synthetic, not synchronized; actual integration requires documented APIs,
   mapping and source-of-truth decisions.
5. Render file storage is ephemeral; SQLite is local only. For production persistence migrate DB
   to durable storage. Do not enable public send until credentials/domain, allowlist and origin settings reviewed.
6. A different local date will change the 'next 60 days' queue; synthetic dates are around Oct 2026.
7. The supplied `SESSION_NOTES.md` replaces the previously near-empty `# Session Notes` stub.

## 7. Next agent instructions

First read this file, `AGENTS.md`, `RUN_VOR_HUB.md`, and the new API/UI modules.
Do not start over. Fix tests or user-reported local UI issues within this isolated feature.
Keep password and all provider credentials server-only; don't add this route to the public menus.
Do not modify the main portfolio layout or existing endpoints to make the demo look right.

## 8. Quick commands (Windows PowerShell, repo root)

```
git switch -c feat/fleet-vor-hub-demo
py -3 scripts/install_vor_hub.py
.\scripts\start-vor-backend.ps1      # terminal 1
.\scripts\start-vor-frontend.ps1     # terminal 2
```

URL: `http://localhost:3000/fleet-vor-hub`, demo password: `Victoria`

## 9. Verification

Backend API pytest included (`backend/tests/test_vor_demo.py`).
Run from backend folder:
`uv run --extra dev pytest tests/test_vor_demo.py -q`.
Frontend: `npm run typecheck`, `npm run lint`, `npm run build`.
Package preparation: API tests **2 passed** with pytest. Frontend TypeScript syntax transpilation completed without diagnostics; `npm run build`, full TypeScript typecheck and browser E2E were **not run** (no installed frontend dependencies in packaging environment).
