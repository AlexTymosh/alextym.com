# HTTP 503: расследование, исправление и IAM runbook

Проверено **2026-11-24**, ветка `feat/preferans-release` от `69a8ece`.
Локальный патч не применяет облачные изменения и не означает production sign-off.

## 1. Подтверждённый дефект SDK и проверенный IAM-блокер

**Production-привязка IAM ещё не установлена.** Пользователь пока не уверен,
какой service account настроен в текущем Render secret. Поэтому live IAM-ошибка
проверенного известного Render principal не объявляется окончательно доказанной
причиной production history/rankings. Логи подтверждают их 503, но не сохраняют
исключение. Нужна сверка `client_email` либо новая безопасная диагностика после
пользовательского развёртывания патча. Кодовый SDK-дефект подтверждён независимо.

**IAM — блокирующий этап для проверенного аккаунта.** У известного Render service
account в `portfolio-lab-dev` есть `firebaseauth.users.get` и
`datastore.entities.get`, но отсутствуют:

```text
datastore.entities.list
datastore.databases.get
datastore.entities.create
datastore.entities.update
```

Актуальным локальным ключом этого аккаунта успешно прочитан отдельный документ,
но реальные запросы `preferans_results` и `preferans_rankings` получили
`PermissionDenied`. Read-only `projects/portfolio-lab-dev:testIamPermissions`
вернул HTTP 200 и подтвердил отсутствие четырёх прав. Такой набор прав позволяет
читать отдельные control-plane документы, но не выполнять запросы/запись
Preferans. Связь с текущим production principal требует отдельного подтверждения.

**SDK — второй независимый дефект.** `_get()` считал результат
`Transaction.get(ref)` одним `DocumentSnapshot`. В реальном Python SDK это
генератор. Настоящий Firestore Emulator воспроизвёл
`AttributeError: 'generator' object has no attribute 'exists'` при создании
комнаты. Старый Fake возвращал snapshot и скрывал проблему.

`@transactional` начинает транзакцию перед callback. Поэтому при текущих
проверенных IAM-правах создание сначала блокируется на BeginTransaction;
после добавления прав старый `_get()` всё равно сломается. Этот порядок следует
из кода SDK; старые production-логи не сохраняли тип исключения.
**При использовании этого principal нужны и исправление IAM, и патч SDK-чтения.**
Если в Render используется другой аккаунт, сначала проверить его фактические
разрешения; не переносить диагноз или менять роли по предположению.

Проверенный ключ принадлежит известному Render runtime principal из настройки
проекта. Production `FIREBASE_SERVICE_ACCOUNT_JSON` через MCP не читался.
Перед изменением IAM сопоставить его `client_email` с этим principal приватно,
без публикации JSON. Аккаунт или ключи заменять не требуется.
Устаревший локальный development-сертификат был отклонён при отдельной попытке;
это не доказывает неисправность credentials на Render. Диагноз IAM основан на
последующей успешной проверке актуального ключа, а не на этом отказе.

Нет доказательств отсутствующей базы, неправильных production credentials или
необходимости предварительно создавать коллекции. `datastore.databases.getMetadata`
тоже отсутствует у проверенного аккаунта, но для игрового API оно не нужно.

## 2. Доказательства инцидента

- Render: `alextym-backend`, `srv-d8b22qh9rddc7386qf0g`, выбранный пользователем
  workspace `tea-d8b1inf7f7vs73bksor0`.
- 2026-11-24 09:49:59 UTC: `/preferans/history` и `/preferans/rankings` — 503;
  request IDs `req_5df5ee0e074349ebacb70dcd8c27df7b`,
  `req_225d8bbd14994d12b4b2b0b4fb0f952c`.
- 09:51:28 UTC: `POST /preferans/rooms` — 503,
  `req_74eb5258a89b491ebe6d4a9e754e2cfb`.
  FastAPI получил запросы после BFF. Поиск error/warn за время инцидента не дал
  причины: обработчик переводил SDK-ошибки в 503 без диагностической записи.
- Реальный SDK: `firebase-admin 7.8.0`, `google-cloud-firestore 2.34.1`.
- До патча настоящий эмулятор читает пустые историю/рейтинг, но create падает
  на генераторе. После патча проходят create/replay/join/start/первый `pass`.
- После исправления семантики Fake старый код даёт **5 failed / 7 passed**
  в `test_secure_rooms.py`; исправленный код проходит этот regression.

Production-записи, удаление данных и пробное создание production-комнаты не
выполнялись. Ключи, токены, настоящие UID и содержимое документов не включены
в логи или этот отчёт.

## 3. Путь запроса и все источники 503

`Browser → Next.js /api/preferans/* BFF → FastAPI /api/preferans/*
→ Firebase Admin SDK → существующая Firestore (default)`.

| Участок | Источник HTTP 503 |
|---|---|
| BFF `route.ts` | Исключение `labProjectAccess`: `Access unavailable`; upstream 503 передаётся клиенту. Ошибка fetch/тайм-аут/невалидный upstream — 502. Fallback rewrite не заменяет существующий BFF route. |
| `firebase_identity.py` | Нет Owner UID: `Lab unavailable`; ошибка admission lookup: `Admission unavailable`. Некорректный credential даёт 401. |
| `project_grants.py` | Ошибка чтения гранта: `Project access unavailable`. Нет подходящего гранта — 403. |
| `online/router.py` | Инициализация именованного app/client и неожиданные ошибки операций: `Storage unavailable`; `StoreError` сохраняет свой статус. Media имеет собственный generic 503. |
| `online/store.py` | Нет или повреждено private/game/score state, некорректный final accounting/invitation, рейтинг больше поддерживаемой границы. |
| `online/controls.py` | `Undo snapshot unavailable`, `Counter requires operator review`: `ControlError(503)` переводится в `StoreError`. |

`backend/app/main.py` монтирует весь router с `require_preferans_member`.
FastAPI независимо проверяет Firebase token/session, admission и актуальный
грант проекта, включая прямые Render-запросы. BFF проверяет свой session cookie,
права, Origin POST, JSON и разрешённый upstream path. Эти правила не меняются.

SDK получает именованный app `portfolio-lab`, ранее созданный проверкой
credential в `firebase_identity._firebase_app()`, с проверкой project ID.
Проектные `Test`/`Admin`/`View`, pinned Owner и отзыв гранта сохраняются.

Пути корректно чередуют collection/document:
`preferans_create_ops/{hash}`, `preferans_rooms/{id}`,
`preferans_rooms/{id}/private/current`, `operations/{hash}`, `events/{seq}`,
`preferans_results/{id}`, `preferans_rankings/{player_id}`.
Пустые коллекции законно возвращают пустые массивы; ручное создание документов
не исправляет IAM. Схемы Pydantic по-прежнему запрещают extra fields.
Create/start/command реально сериализуются SDK в эмуляторе. Нет миграций,
новых индексов, схем или зависимостей.

## 4. Изменения кода и диагностики

`_get()` теперь вызывает `ref.get(transaction=tx, timeout=5.0)`: один snapshot
в той же транзакции. Все чтения остаются перед записями. Atomic receipts,
create preconditions, версии и идемпотентность сохранены. Общий helper
исправляет также mutations, финализацию и использующий его Preferans media.

Router пишет allowlisted JSON-сообщение `preferans.storage.failed` с
`operation`, `stage` (`initialization`/`operation`/`state`), `error_type`,
опциональным `cause_type`, `request_id` из host middleware. Стандартный logger
помещает JSON-сообщение в структурированный host envelope; тот же ID есть в
`http.request.completed`. Нет exception text, traceback, provider metadata,
UID, credentials, payload, idempotency keys, карт или game state.
HTTP-ошибки остаются общими и сохраняют прежние статусы.

Fake теперь моделирует генератор `Transaction.get`, snapshot
`DocumentReference.get(transaction=...)`, запрет read-after-write, отложенные
create preconditions и атомарный отказ batch. Query не читает подколлекции и
не включает документы без поля сортировки. Fake не моделирует Google IAM,
сеть и конкурентный планировщик; отдельные emulator/live-проверки обязательны.

## 5. Исправление конфигурации оператором

Облачные изменения этой работой **не применялись**.

1. В `Render → alextym-backend → Environment` приватно проверить project ID
   и `client_email` текущего `FIREBASE_SERVICE_ACCOUNT_JSON`. Не публиковать JSON.
2. В `Google Cloud → portfolio-lab-dev → IAM & Admin → IAM` найти этот service
   account и назначенную ему custom runtime role. Vercel использует другой
   principal; изменение его роли не исправляет Render.
3. `IAM & Admin → Roles → эта custom role → Edit role → Add permissions`:
   добавить четыре разрешения из раздела 1, **сохранив существующие**.
   `entities.get/list` нужны запросам; `databases.get` — BeginTransaction/Rollback;
   `entities.create/update` — Commit. Не добавлять Owner/Editor, delete или
   `getMetadata`, не менять сервисный аккаунт, ключи и deny-all client rules.
4. Дождаться применения IAM. Развернуть патч после пользовательских commit/push/PR.
   До применения обоих исправлений create не считается восстановленным.
5. Выполнить post-deploy сценарий ниже. Новая база, платные сервисы и Firestore
   TTL не нужны; TTL не включать.

CLI-эквивалент с уже авторизованным операторским `gcloud`:

```powershell
$projectId = 'portfolio-lab-dev'
# Взять фактический ID назначенной Render custom role из IAM Console.
$renderRoleId = '<confirmed-render-custom-role-id>'
gcloud iam roles describe $renderRoleId --project=$projectId --format=json
# --add-permissions сохраняет другие разрешения роли.
gcloud iam roles update $renderRoleId --project=$projectId '--add-permissions=datastore.entities.list,datastore.databases.get,datastore.entities.create,datastore.entities.update'
```

Не заменять `--add-permissions` сокращённым `--permissions`: последний может
удалить необходимые прежние права.

## 6. Воспроизведение и проверки

Команды из корня, отдельный тестовый терминал. Сначала запустить оба эмулятора:

```powershell
firebase emulators:start --only auth,firestore --project demo-preferans-503 --config infra/firebase/firebase.json
```

Во втором терминале:

```powershell
task backend:sync
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.tmp/uv-cache'
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.tmp/backend-venv'
$env:PREFERANS_EMULATOR_TESTS = 'true'
$env:FIREBASE_PROJECT_ID = 'demo-preferans-503'
$env:FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:19099'
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:18080'
uv run --project backend python -m pytest backend/tests/test_preferans_firestore_emulators.py -q
Remove-Item Env:PREFERANS_EMULATOR_TESTS, Env:FIREBASE_PROJECT_ID, Env:FIREBASE_AUTH_EMULATOR_HOST, Env:FIRESTORE_EMULATOR_HOST

task repo:check
task backend:check
task frontend:check
task ci
```

Opt-in fixture требует `demo-*`, оба strictly loopback emulator hosts и
отсутствие `RENDER`/`VERCEL`. Реальные credentials удаляются только из окружения
тестового процесса. Синтетические пользователи и данные не удаляют production.
Backend auth/grants не подменяются dependency overrides.

| Выполненная проверка | Результат |
|---|---|
| Старый код с исправленным Fake | 5 failed / 7 passed, тот же AttributeError; затем regression исправлен |
| `task repo:check` | PASS: hygiene, registry, границы трёх проектов |
| `task backend:check` | PASS: lint/format/imports/compile; 1327 passed, 8 skipped (4 optional Redis + 4 отдельно запускаемых emulator) |
| `task frontend:check` | PASS: install/lint/typecheck/resume/build; 444 passed, 50 режимозависимых skipped |
| Настоящие Auth/Firestore Emulator через FastAPI | 4 passed: ID token/session, пустые запросы, create/replay/join/start/command, приватность, 401/403, отзыв гранта, конкурентная атомарность |
| Настоящий локальный Next.js BFF → FastAPI → Admin SDK → оба Emulator | 17 HTTP assertions passed: 201/200, повтор без дубля, 401/403, hostile Origin 403, private path 404 |
| Production site и прямой Render без credentials | Четыре read-only GET history/rankings вернули 401; авторизованное восстановление это не доказывает |
| `task ci` | 7/8 PASS: repository/config/wizard/deployment/backend/RAG/Docker прошли; frontend: 443 passed, 50 skipped, 1 failed при `page.goto('/resume')` с `net::ERR_ADDRESS_IN_USE` |
| Изолированная проверка упавшего mobile `/resume` теста | 1 passed, без изменения кода, `--workers=1 --retries=0`, отдельный localhost-порт вне sandbox |
| Последующий прогон владельца | Пользователь подтвердил зелёные проверки; новые логи агент отдельно не просматривал |

Первоначальный запуск `task ci` агентом остаётся записан как неуспешный;
впоследствии владелец подтвердил зелёные проверки. Отказ `/resume` произошёл при
сетевом открытии страницы до действий теста; начальный полный
`task frontend:check` прошёл все 444 теста. Повтор упавшего сценария:

```powershell
Push-Location frontend
$env:PLAYWRIGHT_USE_EXISTING_BUILD = 'true'
$env:PLAYWRIGHT_PORT = '14388'
npm run e2e -- e2e/resume.spec.ts --project=mobile-chrome --grep='sorts visible entries by section before date' --workers=1 --retries=0
Pop-Location
```

В текущей среде localhost-проверки потребовали выполнения вне network sandbox.
Первый изолированный запуск внутри sandbox был остановлен; указанный запуск
вне sandbox завершился успешно. Код Resume, тестовые ожидания и конфигурация
CI не менялись ради устранения этого отказа. Причина первоначальной коллизии
сокета отдельно не установлена. Изолированный повтор не подменяет полный CI;
сведения о последующем зелёном прогоне получены от владельца.

Эмулятор 1.22.0 при двух одновременных create с одним ключом может дать
`Transaction lock timeout`, затем настоящий HTTP 503 после пяти штатных
попыток SDK. Конкурентный тест **явно допускает этот отказ** и проверяет
отдельный повтор с тем же ключом и ровно одну комнату. Он не обещает 201 каждому
конкурентному запросу или production latency. Последовательный replay обязан
давать 201 с тем же ответом. В приложение не добавлены новые повторы или
фиктивные успешные ответы. Production contention остаётся отдельным измерением.

Существующие предупреждения: 7 Fleet ESLint warnings, Starlette/httpx deprecation,
8 moderate npm audit findings. Зависимости не изменены; общего security
release sign-off эта работа не даёт.

## 7. Post-deploy и оставшиеся ограничения

- Сопоставить фактический Render principal и подтвердить четыре IAM-права.
- Admin: history/rankings 200. При отсутствии результатов — пустые массивы;
  при наличии партий проверить данные, не очищая коллекции ради теста.
- Одна согласованная тестовая комната — 201; повтор с тем же ключом возвращает
  тот же ID без второго room/receipt. Два Test/Admin подключаются, администратор
  начинает раздачу, первый допустимый ход даёт 200. Видна только своя рука.
- Без credential — 401, с admission без Preferans grant — 403, также напрямую
  на Render. Грант другого проекта не заменяет Preferans.
- При 503 сопоставить `preferans.storage.failed` и `http.request.completed` по
  request ID. Не публиковать provider errors, токены и private state.

Production IAM mutation, redeploy и production 201/200 не проверялись.
Автоматический доступ к текущему Google Chrome отклонён; локальная BFF-проверка
выполнена HTTP-клиентом. Эмулятор не реализует Google Cloud IAM. Полный UAT
трёх устройств, медиа и прежние house-rule release gates остаются отдельными.

Изменённые файлы: `online/store.py`, `online/router.py`,
`tests/test_secure_rooms.py`, новый `tests/test_storage_diagnostics.py`, новый
`backend/tests/test_preferans_firestore_emulators.py`, Preferans README,
Preferans `backend/README.md` и `tests/README.md`, `SESSION_NOTES.md`, этот
runbook и `docs/deployment.md`.
Fleet/Workforce, Firebase Authentication, grants, client rules, документы
Firestore и публичные API-форматы не меняются.

Основания: [Python Transaction.get](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.transaction.Transaction),
[Firestore IAM и права RPC](https://firebase.google.com/docs/firestore/security/iam).
