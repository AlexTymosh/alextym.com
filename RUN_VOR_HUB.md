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

Скрипт использует текущий `backend/.env` (если есть), затем `uv run` и порт 8000.
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
