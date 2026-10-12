# Fleet VOR Hub — запуск на Windows 11 / PyCharm

Проект: `https://github.com/AlexTymosh/alextym.com`.
Создаём ветку `feat/fleet-vor-hub-demo` и НЕ выкладываем демо напрямую в production.

## A. Установка (один раз)

1. Открой корень локального проекта `alextym` в PyCharm, затем **Terminal → PowerShell**.
2. Выполни:

```powershell
git status --short
git switch main
git pull --ff-only
git switch -c feat/fleet-vor-hub-demo
```

Если уже находишься в нужной ветке, не создавай её второй раз. Если `git status`
содержит изменения, сначала сохрани их отдельно; не удаляй.

3. Распакуй **содержимое** ZIP прямо в корень проекта, чтобы появились
   `frontend/app/fleet-vor-hub/page.tsx`, `backend/app/api/vor.py`,
   `scripts/install_vor_hub.py`, `SESSION_NOTES.md` и др.
   Не копируй ZIP внутрь `frontend` или `backend`.
4. Зарегистрируй новый роутер безопасным установщиком:

```powershell
py -3 scripts/install_vor_hub.py
```

Установщик делает точечную правку `backend/app/main.py`, сохраняет оригинал в
`backend/_local/vor_install_backup/main.py.before_vor`, не переписывает существующие маршруты.

## B. Запуск (две консоли PowerShell)

### Консоль 1 — FastAPI

Из корня проекта:

```powershell
.\scripts\start-vor-backend.ps1
```

Скрипт использует текущий `backend/.env` (если есть), затем `uv run --no-sync` и порт 8000.
Он включает демо только в локальном процессе, задаёт пароль `Victoria`,
отключает настоящую отправку почты. Для изменения пароля в той же консоли
перед запуском выполнить:

```powershell
$env:VOR_DEMO_PASSWORD = "my-new-password"
.\scripts\start-vor-backend.ps1
```

### Консоль 2 — Next.js

Из корня проекта:

```powershell
.\scripts\start-vor-frontend.ps1
```

Этот скрипт на время процесса задаёт `BACKEND_ORIGIN=http://127.0.0.1:8000`
и выполняет `npm run dev` внутри `frontend/`.
Если нет `node_modules`, сначала:

```powershell
cd frontend
npm ci
cd ..
```

Если PowerShell блокирует `.ps1`, разреши скрипты **только в текущем процессе**:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Если `uv` не установлен, установи его по официальной инструкции `https://docs.astral.sh/uv/`.

### Открыть

`http://localhost:3000/fleet-vor-hub` → пароль `Victoria` (или твой).

Проверка API: `http://127.0.0.1:8000/api/vor/session` (в браузере покажет JSON).
Другие API требуют авторизацию через cookie после входа через сайт.

## C. Что проверить вручную

1. **Vehicles:** отображаются 20 машин с индивидуальными границами; карточка справа меняется при выборе.
2. **Workflow:** у разных неисправностей различаются этапы; `Complete stage` сохраняет изменения в SQLite.
3. **Chatter:** internal note создаёт новое событие, привязанное к машине и тикету.
4. **External email:** сначала сообщение только имитируется и сохраняется; это явно подписано.
5. **Subscribers:** `Manage` добавляет внешнего участника и подписывает на автомобиль.
6. **Dashboard:** 4 KPI + VOR chart + fault distribution + priority list.
7. **Calendar:** месяц назад/вперёд; видны забронированные MOT, Inspection, Service с garage;
   справа due-within-60-days, не имеющие брони; `Book` создаёт appointment.
8. Refresh браузера — созданные сообщения/бронирования сохраняются.

## D. Где хранятся данные

- Seed (не меняется): `backend/app/services/vor_seed.sqlite3`
- Текущая локальная база: `backend/_local/vor_hub.sqlite3` (создаётся автоматически)
- Для сброса демо: **останови backend**, затем удали ТОЛЬКО файл
  `backend/_local/vor_hub.sqlite3`. При следующем старте он создастся заново из seed.

## E. Настоящие email (не включать до настройки)

Default: `VOR_DEMO_SEND_REAL_EMAIL=false` — отправка только демонстрируется.
Для последующего live-теста на backend нужны:

```
VOR_DEMO_SEND_REAL_EMAIL=true
RESEND_API_KEY=<your existing provider secret>
VOR_DEMO_FROM_EMAIL=demo@your-verified-domain.example
VOR_DEMO_ALLOWED_RECIPIENTS=your-allowed-email@example.com
VOR_DEMO_EMAIL_LIMIT=15
```

Эти значения задаются через приватное `backend/.env` или окружение процесса.
В Windows start-script в текущем пакете принудительно оставляет real-email выключенным;
перед live-тестом нужно осознанно изменить это поведение и проверить отправителя,
allowlist и `Origin`. Real email ограничен backend и не зависит от UI.
`VOR_DEMO_ALLOWED_ORIGINS` нужен только при нестандартном reverse proxy.

**Входящие email не реализованы.** Для их добавления нужен inbound webhook и корреляция
по `Message-ID` / `In-Reply-To` / ticket reference.

## F. Проверки

Из `backend/`: `uv run --extra dev pytest tests/test_vor_demo.py -q`
Из `frontend/`: `npm run typecheck`, `npm run lint`, `npm run build`
Из корня: `git diff --stat`.

## G. Важные границы

- Маршрут не добавлен в навигацию сайта; `robots: noindex`.
- Все имена/почты машин/поставщиков — тестовые, не надо переносить реальные служебные сведения.
- SQLite подходит для локального MVP, но на обычном Render-деплое файловая система может быть непостоянной.
- Не коммить `backend/.env` и `backend/_local/`.
- `SESSION_NOTES.md` описывает цели, архитектуру и дальнейшие шаги для следующего агента.

## UI v1 incremental update

Если Fleet VOR Hub уже работает, см. `UPDATE_VOR_HUB_V1.md`: файлы заменяются поверх предыдущей версии, повторный установщик не нужен. Новая версия добавляет Г-образный layout, PS000xxx, экспорт Excel/ICS и миграцию с сохранением пользовательских данных.


## Incremental upgrade (v1.1, October 2026)

If v1 already runs, do not reinstall dependencies or run `install_vor_hub.py` again. Stop both terminals, extract `fleet_vor_hub_v1_1_patch.zip` into the repository root with overwrite, then use the unchanged backend and frontend launch scripts. See `UPDATE_VOR_HUB_V1_1.md`.

The highlighted top vehicle panel now contains Maintenance & Compliance dates, the workflow stages are vertical with Next action alongside, and 13 selectable workflow scenarios reset only the selected open ticket's progress (with confirmation). The responsible employee is selected from five names and persisted.

## v1.2 incremental patch — installation and live email configuration

**Existing v1.1 installation required.** Stop both development servers. Extract the `fleet_vor_hub_v1_2_patch.zip` content into the repository root `alextym/`, keeping paths and overwriting matching files. **Do not delete `backend/_local/vor_hub.sqlite3`**. There is no need to reinstall dependencies or rerun `install_vor_hub.py`.

Start both terminals:

```powershell
.\scripts\start-vor-backend.ps1
.\scripts\start-vor-frontend.ps1
```

Open `http://localhost:3000/fleet-vor-hub` and refresh with Ctrl+F5. Password remains the value of `VOR_DEMO_PASSWORD` (default for the script: `Victoria`). On first load, SQLite will apply one versioned migration with four contacts and some overdue MOT/Inspection/Service dates. This migration leaves previously saved messages and bookings intact.

To test **without actually emailing anyone** leave `VOR_DEMO_SEND_REAL_EMAIL=false` (default). Clicking **External email** shows the current vehicle subscribers, Subject and a message textarea. Clicking Send records an outbound simulated event and its recipients in the Chatter. No email leaves the application.

For **actual** mail, after a public reachable demo page is deployed and email sender verified, configure `backend/.env` (do not commit it):

```dotenv
VOR_DEMO_SEND_REAL_EMAIL=true
VOR_DEMO_ALLOWED_RECIPIENTS=alex@YOUR-ALLOWED-DOMAIN,victoria@YOUR-ALLOWED-DOMAIN
VOR_DEMO_EMAIL_LIMIT=15
VOR_DEMO_FROM_EMAIL=demo@YOUR-VERIFIED-DOMAIN
VOR_DEMO_PUBLIC_URL=https://YOUR-DOMAIN/fleet-vor-hub
RESEND_API_KEY=YOUR-API-KEY
```

For the selected vehicle open **Subscribers → Manage** and turn **off** the fictional external subscriber before live-send testing; the two required addresses should stay checked. Any nonallowlisted subscriber causes rejection, rather than silent partial delivery. `VOR_DEMO_EMAIL_LIMIT` counts recipient deliveries (two recipients = two of 15). Emails contain notification text and a link to read the newly recorded update, not the full draft.

Testing: from `backend/`: `uv run --no-sync --extra dev pytest tests/test_vor_v1_2.py -q`. On Windows, `uv run --no-sync python -m pytest tests/test_vor_v1_2.py -q` may work if pytest is already installed; otherwise use the project's normal backend test command. In `frontend/` run `npm run typecheck` and `npm run build`. No production deployment is included.

To configure both internal contact email addresses without manually editing `.env`, run:

```powershell
.\scripts\configure-vor-subscribers.ps1 -AlexEmail "YOUR-ALEX-ADDRESS" -VictoriaEmail "YOUR-VICTORIA-ADDRESS"
```

Then restart backend so both addresses are synchronised into the SQLite contact directory.

---

## v1.3 IMPORTANT UPDATE (supersedes older subscriber scripts)

Email addresses are now added/edited from **Manage** in Fleet VOR Hub. Do not run the old `configure-vor-subscribers.ps1` helper. Existing private contact env values are not re-synced after a database has been migrated. Changing `Manage` contacts is persisted to SQLite and controls all vehicle subscribers.

For live delivery after deployment, consult `UPDATE_VOR_HUB_V1_3.md`; backend `VOR_DEMO_SEND_REAL_EMAIL=true`, Resend key, verified sender, public URL and at least one allowed **domain** or exact approved address are required. Specific email addresses do **not** have to be listed in environment variables if their domain is permitted. Render Free SQLite data is ephemeral and contact changes disappear at service restart; use durable storage for reliable production use.
