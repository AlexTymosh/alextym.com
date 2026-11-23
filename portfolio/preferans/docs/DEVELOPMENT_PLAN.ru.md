# «Преферанс по-запорожски» — анализ архитектуры и подробный план разработки

**Идентификатор:** `preferans`
**Рекомендуемое размещение:** `portfolio/preferans/`
**Маршрут:** `/portfolio/preferans`
**API (после появления защищённого доменного backend):** `/api/preferans`
**План:** v1.0, 22 ноября 2026 г.
**Источники:** текущее состояние ветки `main` репозитория `AlexTymosh/alextym.com` при анализе, `FULL_TECHNICAL_SPECIFICATION.ru.md`, `HOUSE_RULES.ru.md`, действующие архитектурные контракты проекта.
**Статус (23.11.2026):** PR 1 объединён с `main` в #268 (`e7a2a6d`); PR 2 готов как локальный архив чистого Python-движка, ожидает применения, пользовательских CI-проверок и merge. PR 3–9 ещё не реализованы.

> **Правило источника истины.** Игровые правила — `docs/HOUSE_RULES.ru.md`; полный перечень принятых требований — `docs/FULL_TECHNICAL_SPECIFICATION.ru.md`; инженерные решения/отклонения — в настоящем плане и последующих ADR. Любое расхождение новых решений с историческими правилами требует отдельного согласования, а не скрытого изменения алгоритма.

## 1. Исследование фактического репозитория

Проверено GitHub Contents и Git tree на `main` (22.11.2026; в дереве 905 элементов, SHA дерева `491a909c65dbbecf0110d600c9d9516cf2e84d65`). Перед каждым PR перепроверять **новую** голову `main`: содержание может измениться после создания этого ZIP.

| Узел | Подтверждённая реализация | Следствие для «Преферанса» |
|---|---|---|
| `portfolio/README.md` | Каноническая папка для embedded-модулей; свои `frontend/`, `backend/`, `tests/`, `docs/` | Не создавать отдельный репозиторий, приложение или самостоятельный деплой |
| `portfolio/catalog/registry.json` | Сейчас зарегистрированы `fleet_hub`, `workforce_intelligence` | Зарегистрировать `preferans`, но `catalog.visible=false` до security gate |
| `scripts/check-portfolio-registry.mjs` | Требует manifest, readme в трёх директориях, страницу на заявленном маршруте | Даже foundation PR должен содержать host route, project files и frontend/src |
| `scripts/check-registered-project-boundaries.mjs` | Проверяет локальные импорты и запрет глобальных CSS у **каждого** зарегистрированного модуля | Компоненты и CSS Modules только в `portfolio/preferans/frontend/src` |
| `scripts/check-no-raw-cyrillic.mjs` | Русский текст разрешён только в именах с `.ru.` | Правила/ТЗ/план именовать `*.ru.md`, русские UI-строки хранить в `content.ru.json`; `SESSION_NOTES.md` писать по-английски |
| `frontend/tsconfig.json` | Существуют только alias `@fleet-hub`, `@workforce-intelligence` | Добавить ровно один публичный alias `@preferans` |
| `frontend/app/portfolio/…` | Тонкие Next.js adapter routes, метаданные `noindex` | Защищённая страница без новой глобальной навигации |
| `frontend/lib/portfolio-lab/project-access-server.ts` | Сессионная cookie; `requireLabProjectPage(projectId)`; сверка гранта из Firestore | Использовать проектный grant; **проверять** отключённый Lab: функция сама по себе тогда no-op |
| `frontend/lib/portfolio-lab/project-grants.ts` | `View`, `Test`, `Admin`; read/write split; `Owner` глобально | Логика комнат — дополнительная роль, а не самостоятельная система аккаунтов |
| `backend/app/security/firebase_identity.py`, `project_grants.py` | Проверка реального Firebase credential и гранта; отсутствие доступа fail-closed | Прямой Render URL должен отклонять неавторизованные команды, не полагаться на frontend |
| `backend/app/main.py` | Host монтирует публичные routers Fleet/Workforce | Добавить backend mount только вместе с полноценным auth dependency и тестами; не в первом PR |
| `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile` | uv path dependencies и установка модулей в один Docker | Добавление `preferans` Python package потребует синхронного обновления всех трёх, тестов и lock-файла |
| `frontend/scripts/link-portfolio-deps.mjs` | Используется один `frontend/node_modules`, проектам создаются junction/symlink | Не добавлять вторую frontend dependency tree |
| `frontend/next.config.mjs` | `/api/*` rewrite как fallback на Render | Для защищённых запросов не отправлять браузерную cookie напрямую в Render; нужен BFF с проверкой гранта и Firebase credential |
| `Taskfile.yml`, `.github/workflows/ci.yml` | `task ci` и 5 CI jobs: project/backend/frontend/rag/docker | Не удалять и не ослаблять проверки, не обещать что локальный тест заменяет полный CI |
| `portfolio/workforce_intelligence/SESSION_NOTES.md` | Большие living notes с PR/checkpoint/status | Для нового проекта — короткий, строго актуальный handoff по фактам, без мнимых «готово» |

### Важные отличия от модулей Fleet и Workforce

1. **Игра — постоянная многопользовательская система**, а не сбрасываемое демо. Незавершённая партия сохраняется до завершения/архивации. Render-local SQLite (как в Fleet/Workforce) не годится для источника истины.
2. **Скрытые карты — доверительная граница.** Клиент должен получать лишь собственную руку + публичные карты, никогда чужую колоду или полное игровое состояние через props, DevTools, общие документы Firestore.
3. **Важна конкурентность**, а не только CRUD: два клиента могут одновременно подать команду; допустим только один переход состояния и одно начисление.
4. **Не все видеосоединения гарантированно работают без TURN.** При жёстком бюджете £0 нужен проверяемый P2P-прототип, диагностируемый отказ и возможность играть без камеры/микрофона. Платный relay не добавлять молча.
5. **Render Free не always-on.** Он может уснуть после 15 минут неактивности и перезапуститься; таймеры не должны зависеть от памяти работающего процесса.
6. **Русский UI при англоязычном каталоге**: не ломать репозиторный Cyrillic guard, не добавлять русский текст в публичный portfolio card.

## 2. Архитектурное решение и альтернативы

### 2.1. Рекомендуемое решение (основной вариант)

Существующий модульный монолит сохраняется:

- **Next.js / React**: защищённый маршрут `/portfolio/preferans`, frontend проекта под `portfolio/preferans/frontend/src`; реактивная панель торговли, drag-and-drop руки, игровые комнаты, настройки, статистика и рейтинг.
- **FastAPI / Python**: выделенный `preferans` Python package как чистый детерминированный игровой движок; host только импортирует public router, защищённый *shared* Firebase dependency и lifecycle adapter. Доменный код не импортирует `app.*`, Fleet или Workforce.
- **Cloud Firestore**: источник истины для комнат, партий, сохранённых snapshots наборов правил, событий/ledger, результатов и аудита. Отдельный namespace `preferans_*`. Данные не хранятся в Render-local SQLite.
- **Авторизация**: общий Portfolio Lab Firebase Auth и грант `project_id=preferans`; Owner выбирает, кому доступен проект. Отдельная роль администратора игры даёт функции правил и поправок, но не глобальный Owner.
- **Доставка команд**: same-origin Next BFF -> FastAPI, где повторно проверяются credential, project membership, room membership, активный ход, версия, idempotency key и бизнес-инварианты.
- **Реальное время**: выбрать после проверки Auth SDK и безопасности на PR 4 — (A) Firestore realtime listeners на изолированные публичные и per-user projections с Security Rules; (B) авторизованный SSE/WebSocket-сервис через тот же backend. Не раздавать полный state. Предпочтение A, *только если* браузерный Firebase SDK после перезагрузки может легально восстановить user auth без второго небезопасного логина; иначе B.
- **Видеосвязь**: прямой mesh WebRTC между тремя игроками, добровольное включение. Для локальной записи: композиция трёх видеопотоков, общего звука и стола (Canvas + MediaRecorder) в браузере инициатора с согласием троих, без серверной загрузки видео.

### 2.2. Отвергнутые/отложенные подходы

| Подход | Причина не выбирать |
|---|---|
| Новый самостоятельный backend/деплой | Расширяет footprint и расходы, нарушает контракт portfolio |
| Локальный Render SQLite для игры | Эфемерность диска, потеря незавершённых партий при рестарте |
| Все данные игры в одном доступном игрокам Firestore document | Скрытые карты утекут через сетевой ответ независимо от визуального сокрытия |
| Прямые записи игрового состояния из браузера | Клиент сможет подделать раздачу, штраф, своё право хода |
| Только WebSocket без хранения | Проигрывает при перезапуске инстанса и потерянных соединениях |
| Все игровые правила в JS/TS на клиенте | Уязвимая недоверенная логика, две расходящиеся версии расчётов |
| Полный rewrite в Next.js серверные actions | Мог бы убрать cold-start Render, но заставит продублировать/переписать Python-домен; допустимо только если PR4 spike докажет неприемлемость Python-решения |
| Несколько отдельных аккаунтов/логинов | Уже есть Firebase/Portfolio Lab |
| Платный TURN или хранение видео | Нарушает подтверждённый бюджет £0; потребуется отдельное явное решение |

### 2.3. Технический эксперимент — обязательный gate

До тяжёлого PR4 сделать малый вертикальный прототип: 3 Firebase test UID, 1 защищённая комната, 3 клиента в отдельных профилях, один серверно обработанный переход, per-seat read projections и reconnect после рестарта backend. Замерить серверный cold-start, read/write квоты, время доставки и отсутствие доступа к чужим картам. Результаты зафиксировать в `docs/ARCHITECTURE.ru.md` + ADR. Если потоковая схема не работает при существующей auth-cookie/in-memory Firebase Auth, выбрать BFF SSE, а не обход правил Firestore.

**Инженерное ограничение:** нельзя гарантировать постоянно работающую игру и видеосвязь со 100% успешностью при бюджете £0. Реализация должна корректно сообщать о недоступности и восстанавливать состояние.

## 3. Жёсткие архитектурные инварианты

1. `main` не изменяется до прохождения PR review/CI; один короткоживущий feature branch на PR.
2. Только три уникальных Firebase UID занимают игровые места. Грант проекта ≠ место в комнате ≠ game-admin.
3. Карты остальных игроков не передаются даже в скрытом JSON, HTML, hydration, логе, ошибкаx или общей подписке.
4. Только сервер генерирует колоду (CSPRNG + seed, не раскрывать seed до завершения), раздачу, действия, начисления и итог.
5. Любой доменный command: проверка actor/room/phase/turn/expected_version/idempotency_key; атомарно либо успешен один раз, либо не применён.
6. Документ партии содержит ruleset snapshot/hash. Изменение шаблона не меняет уже начавшиеся партии.
7. Правки администратора — append-only compensation events, никогда незаметный rewrite истории; итог `Σ(R_i)=0`.
8. Finished game immutable; действия архивирования незавершённой партии доступны Owner с audit, но не подменяют итоги.
9. Прерывания соединения и перезапуск сервиса не сбрасывают игру; таймер хранит абсолютные timestamps и применяется идемпотентно.
10. View-only grant не может отправлять игровые команды; Test/Admin должны иметь соответствующее room access; Owner — администратор по умолчанию.
11. Существующие Fleet/Workforce/Chat/Resume/Contact/RAG/Telegram и публичные URL неизменны, CSS только local modules, нет импортов чужой доменной логики.
12. Никакие реальные ставки деньгами, платежи или ставки казино не внедряются; «удары» — исключительно шуточная виртуальная статистика.
13. Русский текст в исходниках/документах — в `*.ru.*` ресурсах или Unicode escape, без отключения CI-проверки.

## 4. Математические и игровые инварианты

Полное описание см. полное ТЗ §§5–25, правила в `HOUSE_RULES.ru.md`; здесь нормативные инженерные контрольные случаи.

### 4.1. Ранг торгов и два этапа

`6♠..6NT < 7♠..7NT < 8♠..8NT < misere < 9♠..9NT < misere_without_widow < 10♠..10NT < 10♠NP..10NTNP`.

- Торговля только определяет **минимум**, затем отдельный заказ игры ≥ выигранной ставки. Переход обычной заявки в мизер после прикупа запрещён.
- Первая рука может удерживать равную ставку словом «Здесь», **кроме 6♠**. Паснувший не возвращается.
- Мизер — первая личная ставка, 9 перебивает; мизер БП — только ранее заявлявшему обычный мизер; десятирную БП может заявить любой ещё активный, старшинство мастей сохраняется, максимум — 10 БК БП.
- Ошибочная ставка отменяется единогласно только до следующего чужого действия; 120 с ожидание, иначе отклонение. Не создавать ложный отдельный «подтвердить» клик.
- Сдача: 32 карты, пакеты по 2, 2 прикуп, 10 на игрока. Следующий сдающий определяется подтверждённым порядком.

### 4.2. Значения и формулы

`C(n)=2×(n-5)` для n=6..10: `2,4,6,8,10`; мизер и десятирная БП — 10.

- Обычный контракт: `hill_declarer=max(0,ordered-tricks)×C`; выигрыш при успехе `+C` (без бонуса за сверхвзятки).
- Мизер: `tricks_taken×10` в гору, при нуле +10 положительных очков.
- Активный вистующий: `2×C` вистов за защитную взятку; если он единственный — за все защитные взятки.
- Консоляция **обоим** защитникам, даже пасовавшему: `2×C×missing_declarer` вистов на заказчика каждому.
- Штраф одного вистующего: `max(0,required-total_defence_tricks)×C`; нормы 6→4, 7→2, 8→1, 9→1, 10→1.
- Два вистующих: нормы 6→4, 7→2, 8→2, 9→1, 10→1; персональные таблицы из полного ТЗ. Формула двух защитников на 6/7/8 **выведена из подтверждённых примеров**, закрепить property/golden-tests.
- Распасы: уровни 6/7/8, взятка в гору 1/2/3; при нуле +1/+2/+3 положительных очка. Масть первых двух ходов задаёт открытая карта прикупа даже при отсутствии этой масти у первой руки.
- Если пуля закрыта и нечётный 1 балл помощи на равных соперников: каждому по 5 вистов, пули остаются целыми.
- Финальная раздача: остаток 4 очка при всех закрытых пулях = +20 вистов на каждого соперника.
- Сведение горы: `G_i=round(10×H_i/3)` от **всей** горы, `R_i=Σ_{j≠i}(W_ij-W_ji+G_j-G_i)`; ∑ R=0.
- Пример H=[2,0,0] -> R=[-14,7,7]; H=[0,3,6] -> R=[30,0,-30].
- Пары: `ceil(abs(R_i-R_j)/50)` виртуальных ударов проигравшему; каждые 10 заменяются 1 голым (или 10 обычных по выбору). «Выбросить листик» — два голых проигравшему, два первых места соперникам.
- Таймер: по 180 сек, любой соперник запускает на участника с обязанностью ходить; каждый полный интервал +3×стоимость текущей максимальной ставки/контракта, до торгов — минимум; начинается новый интервал, действие останавливает таймер. На распасах стоимость без контракта **параметр с явно заданным дефолтом и тестом**, не скрытое допущение.

### 4.3. Critical golden fixtures

1. 6, защитники 1+0, оба вистуют -> 2 и 4 в гору.
2. 6, защитники 4+0, оба вистуют -> штрафов нет.
3. 6, один вистующий взял 1 общую защитную взятку -> 6 в гору.
4. 7, заказчик взял 6, один вистующий, другой пасовал -> консоляция по 8 обоим + 32 обычных вистов вистующему (40/8).
5. 6, заказчик взял 5, оба вистуют 3+2 -> 16/12 вистов.
6. Последняя пуля 18/20, успешная 8 (6 очков) -> 2 себе, 4 остаток, 20/20 вистов против двух соперников.
7. Три равных результата -> никому золотой медали; двое равны по первому месту -> обоим по золотой; «выбросить листик» -> двум по золотой.
8. Все итоговые результаты неизменно суммируются в ноль после любых ручных корректировок.

## 5. Модель данных: минимальный производственный контур

**Раздельные доменные документы:** `preferans_rooms/{roomId}`, `preferans_rulesets/{id}/versions/{version}`, `preferans_games/{id}`, `preferans_games/{id}/events/{seq}`, `preferans_games/{id}/seats/{uid}/view`, `preferans_games/{id}/public/view`, `preferans_games/{id}/ledger/{entryId}`, `preferans_games/{id}/admin_adjustments/{id}`, `preferans_user_preferences/{uid}`, `preferans_stats/{uid}`. Имена — предложение для ADR; закрепить точные пути и Security Rules перед production.

- Server-only `private_state`: колода, чужие руки, прикуп до открытия, PRNG seed, незавершённые тайные сведения.
- Public projection: публичные ставки/открытые карты/статус, **без** скрытых hands или seed.
- Per-user projection: только карты текущего UID, его легальные действия и служебное состояние; Firestore Rules `request.auth.uid==seat_uid` и активная/непросроченная project membership.
- Append-only events: `event_id`, `game_id`, `schema_version`, `expected_state_version`, actor UID, server timestamp, action type, before/after hashes (без секретов), `ruleset_hash`, idempotency key. Нельзя отдавать секретный payload в общей истории.
- Для статистики не полагаться на счётчики, неконсистентно обновлённые с game finish: транзакционный финал или idempotent aggregator/rebuild.
- Очередность `seq` монотонная, транзакция читает текущую версию, записывает event и изменённый projection/ledger. Один business move → одна committed transaction.
- Комнатный admin может корректировать **только финансовый ledger активной партии**; не менять торговлю/снос/карты. Owner хранит правила архивирования.
- `SESSION_NOTES.md` и docs не должны содержать ключей Firebase, реальные UID друзей, секреты, session cookies, карты активных партий.

## 6. API и real-time контракт

Предварительная схема (финальные names закрепляются в OpenAPI/ADR):

- `POST /api/preferans/rooms` — создать комнату (назначенный admin, грант Test/Admin); `GET /.../rooms` — видимый список по правилам доступа; `POST /.../rooms/{id}/join` — занять свободное место.
- `POST /.../rooms/{id}/start` — старт, только после назначения трёх уникальных мест и frozen ruleset snapshot.
- `POST /.../games/{id}/commands` — единый типизированный command envelope (action, expected_version, idempotency key), не множество беззащитных mutating endpoints.
- `GET /.../games/{id}/view` — per-user filtered view; `GET /.../games/{id}/events` — **redacted** public event history.
- `POST /.../games/{id}/adjustments` — game-admin corrections with reason, only active games.
- `GET /.../rulesets`, `POST /.../rulesets`, `POST /.../rulesets/{id}/versions` — typed parameters, Admin/Owner.
- `GET /.../stats`, `GET /.../ranking` — authorised users with project grant; no anonymous access.
- Per-user camera/audio consent/signalling under project namespace; media payloads are **not uploaded** to backend.

**Error contract:** 401 unauthenticated, 403 wrong project/role/seat, 404 no disclosure of inaccessible room, 409 version/action contention, 422 invalid command, 503 storage/compute down; every conflict returns fresh safe version and retry hints, not hidden game state.

## 7. Риск-матрица

| Риск | Вероятность / ущерб | Превентивный gate |
|---|---|---|
| Hidden card leakage через общую Firestore подписку | Средняя / критический | Emulator rules tests + три браузера + inspect network/hydration |
| Двойные ходы, повторный штраф/помощь при retries | Высокая / высокий | transaction, idempotency_key, concurrency and fault-injection tests |
| Render sleep во время активной партии | Средняя / высокий | durable Firestore + reconnect + persisted deadlines + explicit waiting UX |
| Firestore quotas и latency under subscriptions | Средняя / средний | capacity spike; count reads/transactions/second and alert on threshold |
| TURN недоступен при £0 | Высокая для части сетей / средний | WebRTC spike on home/mobile/office; graceful audio/video off |
| Local media recording перегружает Android | Средняя / средний | constrain 360p/720p, detect unsupported codec, stop/recover chunks |
| Админский ручной ledger ломает расчёты | Средняя / высокий | append-only correction, zero-sum invariant and audit |
| Изменение шаблона пересчитывает прошлую игру | Средняя / высокий | immutable ruleset version/hash in snapshot |
| Ошибки спорной формулы двух вистующих | Средняя / высокий | all golden cases + invariant tests, no hand-waving |
| Русский UI ломает repo check | Высокая без дисциплины / низкий | `*.ru.*` docs + `.ru.json`, checker in `task repo:check` |
| Новый module ломает Fleet/Workforce | Средняя / высокий | baseline smoke; no cross imports; full CI in each PR |
| Owner grants mistaken as room auth | Средняя / критический | permission matrix; server tests of View/Test/Admin/roomAdmin |

## 8. План поставки — 9 PR / ориентировочно 20 осмысленных коммитов

**Правило коммитов:** минимально нужные атомарные изменения с доказательствами тестов; не подгонять искусственно под число. Коммиты внутри PR — для сохранения контекста и отката; в `main` каждый PR squash-merge в один публичный commit. Каждый PR начинается от свежего `main`, один открытый рискованный PR за раз. Заголовки коммитов/PR — на английском; тексты docs/внутренней игры на русском.

### PR 1 — Foundation, registry, gated shell, documentation

- **Ветка:** `feat/preferans-foundation` (поставляется в ZIP как patch).
- **Цель:** зарегистрировать отдельный проект с `catalog.visible=false`, alias и закрытой `/portfolio/preferans`-страницей-заглушкой; сохранить полное ТЗ, пользовательские правила, plan и короткий SESSION_NOTES.
- **Коммит 1:** `chore(preferans): register isolated portfolio module and guarded route` — проектная структура, manifest, host adapter, русские ресурсы UI, boundary checker.
- **Коммит 2:** `docs(preferans): add architecture plan, rules and session handoff` — документы, инструктаж и обновление session notes.
- **Изменяемые host-файлы:** `portfolio/catalog/registry.json`, `frontend/tsconfig.json`, новый `frontend/app/portfolio/preferans/page.tsx`; **не** `backend/app/main.py`, **не** CI или чужие модули.
- **Тесты:** `node scripts/check-portfolio-registry.mjs`, `node scripts/check-registered-project-boundaries.mjs`, `node scripts/check-no-raw-cyrillic.mjs` после `git add`; `node portfolio/preferans/tests/check-foundation.mjs`, `task repo:check`, frontend lint/typecheck/build при установленных deps, `task ci` перед PR.
- **Критерий:** route не доступна без Lab и проектного grant; JSON manifest валиден; noindex; public catalog не показывает игру; Fleet/Workforce не изменены.

### PR 2 — Deterministic game engine: cards, auction, play

- **Ветка:** `feat/preferans-engine`.
- **Коммит 1:** `feat(preferans): implement cards, deal and two-stage auction` — 32 карты, 2×deal, widow, заявки, «здесь», пас, мисеры, legal moves, финальное назначение.
- **Коммит 2:** `feat(preferans): implement trick rules, defense and pass-outs` — ходы, козырь, открытие рук, распасы, мизер, предотвращение скрытого раскрытия.
- **Файлы:** `portfolio/preferans/backend/src/preferans/domain/*`, package pyproject, отдельные tests; lock/Docker host изменения только после готовности backend package.
- **Тесты:** полная карточная колода, property rules of trick winner, все ordinals 0–31, 6♠ except here, 9/misere, 10 NP, first hand, exhaustive impossible moves.
- **Готовность:** любые игровые события детерминированно воспроизводятся локально **без БД/HTTP**.

### PR 3 — Financial engine and versioned ruleset model

- **Ветка:** `feat/preferans-scoring`.
- **Коммит 1:** `feat(preferans): add exact scoring and settlement ledger` — пуля, гора, висты, консоляция, полвиста, помощь, 0-сумма, шуточные наказания.
- **Коммит 2:** `feat(preferans): validate immutable rulesets and golden fixtures` — версии набора правил, hash, допустимые диапазоны параметров, golden fixtures, README.
- **Тесты:** утверждённые контрольные примеры; randomized invariants ∑=0; rounding H=1,2,3,6; равные пули; последняя раздача; penalty table 6/7/8/9/10.
- **Готовность:** каждое начисление объяснимо по ledger, альтернативные коэффициенты не меняют историю.

### PR 4 — Security, Firestore persistence, room lifecycle and realtime decision

- **Ветка:** `feat/preferans-secure-rooms`.
- **Коммит 1:** `feat(preferans): authorize room commands and wire backend package` — Firebase grant + room role, BFF, FastAPI router with dependency, no bypass direct Render. Обновить uv.lock, Dockerfile и backend checks **атомарно**.
- **Коммит 2:** `feat(preferans): persist authoritative game events transactionally` — durable rooms, immutable state snapshot, idempotency, per-user projections, admin roles.
- **Коммит 3:** `feat(preferans): add resilient realtime views and reconnect` — выбрать Firestore listeners vs authenticated SSE с документированным экспериментом, no leakage, restart recovery, cold-start.
- **Тесты:** Firebase emulators (Auth + Firestore), threat matrix, chaos/concurrent commands, direct backend 401/403, view masking, N+1 reads, disconnect/restart.
- **Готовность:** трое могут безопасно войти в одну комнату, состояние после перезапуска не потеряно, правила/снимки авторитетны на сервере.

### PR 5 — Playable three-player responsive UI (active after #271)

- **Ветка:** `feat/preferans-game-ui`.
- **Коммит 1:** `feat(preferans): build room lobby, bidding and contract screens` — вход/места/правила/аукцион 2 клика/«здесь», pending undo, final order.
- **Коммит 2:** `feat(preferans): build playable table and draggable hands` — drag/touch sort, open/dark hands, status, last trick shown to all, player-local persistence.
- **Коммит 3:** `test(preferans): cover three-client game flows and accessibility` — E2E 3 contexts, keyboard/mobile/resizing, no server data leak, no phantom transitions.
- **Готовность:** реальная партия проходит от сдачи до завершения без ручной правки базы.

### PR 6 — Timer, approvals, administrative adjustments and presets UI (active after #272)

- **Ветка:** `feat/preferans-game-controls`.
- **Коммит 1:** `feat(preferans): add persisted timer, undo voting and game controls` — 180s repeated penalty, 120s undo, cancel conditions, pause reconnect, last trick requester.
- **Коммит 2:** `feat(preferans): add ruleset editor and audited corrections` — Owner/Admin, append-only ledger, reason, active game only, historical freeze.
- **Тесты:** fake server clock, boundary/race penalties, timeout votes, no double charge, roomAdmin not global Owner, correct manual financial corrections.
- **Готовность:** управление партиями прозрачно, редактирование результатов после finish невозможно.

### PR 7 — Game history, medals, stats and ranking

- **Ветка:** `feat/preferans-history-ranking`.
- **Коммит 1:** `feat(preferans): persist history and compute ranking snapshots` — immutability after finish, win/tie logic, two golds for pairwise ties, tech defeat, received/given punishments.
- **Коммит 2:** `feat(preferans): add sortable leaderboard and temporal charts` — все колонки, ranking by gold by default, responsive chart 3 lines with sort-linked metric/filter, cached aggregates.
- **Тесты:** exact three results, 2 winners, 3 tie none, sheet discard two winners, no double aggregation, filter/sort graph synchronized.
- **Готовность:** все завершённые партии доступны после перезапуска и честно попадают в общую статистику.

### PR 8 — Voluntary WebRTC and local recording + nostalgic backdrop

- **Ветка:** `feat/preferans-media`.
- **Коммит 1:** `feat(preferans): add optional peer media and consent flow` — three-peer mesh, SDP/ICE signals auth + TTL, media off by default, mute/video controls, reconnect.
- **Коммит 2:** `feat(preferans): add consensual local recording and nostalgic scene` — local composite canvas recording only for initiator, 3 consents, consent withdrawal stop, no server media, placeholder apartment image without private likeness.
- **Тесты:** real browser/device matrix, failure on symmetric NAT, MediaRecorder MIME fallback, Android performance, no upload, stop on revocation.
- **Готовность:** core game работает без медиадоступа; совместимые клиенты могут говорить/видеть друг друга и записывать файл локально.

### PR 9 — Accessibility, security hardening and release

- **Ветка:** `feat/preferans-release`.
- **Коммит 1:** `test(preferans): harden multiplayer, privacy and cross-project regressions` — full property tests, load budget and Firestore read-write count, adversarial auth, failure injection.
- **Коммит 2:** `docs(preferans): finalize runbooks, FAQ and production acceptance` — operator runbook, smoke tests, known limitations, project catalogue text EN, enable visibility only after grant security proven.
- **Тесты:** `task ci`, CI five jobs, Docker build, prod auth+role matrix, three browsers, archive/reconnect, hidden card check; existing Fleet/Workforce/Public snapshots.
- **Готовность:** Owner sign-off, production smoke evidence, public English listing, protected Russian game UI, clean revert path.

**Итого:** **9 PR, 20 смысловых рабочих коммитов** (`2+2+2+3+3+2+2+2+2`). Это ориентир, не формальная квота; при отдельном риске можно сделать дополнительный commit или отдельный PR. После squash на `main` останется до 9 понятных commit-записей.

## 9. Стратегия контекста и SESSION_NOTES.md

- Один PR = одна короткая рабочая ветка, один `SESSION_NOTES.md` в корне проекта.
- После **каждого содержательного коммита** обновить: status, active PR/branch, base SHA, last commit SHA, completed/next scope, executed tests and exit codes, known blockers, decisions/spec deviations.
- **Не писать** «CI PASS» до реально выполненного CI. GitHub Actions и локальные тесты отдельно.
- Каждый новый coding session читает: `SESSION_NOTES.md`, план §8 для активного PR, соответствующий раздел полного ТЗ, последний `git status`, актуальный HEAD main.
- При PR merge squash зафиксировать номер PR/squash SHA в notes, открыть **новую** ветку от обновлённого `main`.
- Не копить длинные chat summaries в SESSION_NOTES; накапливающиеся инженерные решения выносить в `docs/adr/`.
- README текущего модуля хранит команды установки, проверки и ссылки на документы; проблема на production — incident runbook + issue, а не секреты в Markdown.

## 10. Набор команд и CI-gate (Windows 11 / PowerShell)

### Проверка перед началом каждого PR

```powershell
git switch main
git pull --ff-only
git status --short
git switch -c feat/preferans-foundation # только для PR 1
```

После распаковки архива применить патч скриптом `apply.ps1` из ZIP. Скрипт проверяет имя ветки и отсутствие локальных изменений, затем выполняет `git apply --check` до модификации файлов. ZIP не содержит секретов.

### PR 1 targeted checks

```powershell
node scripts/check-portfolio-registry.mjs
node scripts/check-registered-project-boundaries.mjs
node portfolio/preferans/tests/check-foundation.mjs
git add portfolio/preferans frontend/app/portfolio/preferans/page.tsx frontend/tsconfig.json portfolio/catalog/registry.json
node scripts/check-no-raw-cyrillic.mjs
node scripts/check-website-portfolio-boundaries.mjs
git diff --cached --check
```

### Полная проверка (когда зависимости уже установлены)

```powershell
task repo:check
cd frontend
npm ci
npm run typecheck
npm run lint
npm run build
cd ..
task ci
```

`task ci` может требовать Docker, `uv`, Task и runtime secrets/config. Запускать в сконфигурированной среде, иначе честно указать ограничения; **не утверждать**, что online Firebase и Render проверены локальными статическими тестами.

### PR 2+ additional

```powershell
task backend:sync
task backend:lint
task backend:format-check
task backend:test
task backend:imports
task docker:build
```

Таргетированные pytest указывать из `backend/` с корректным `uv run python -m pytest ../portfolio/preferans/tests` **после** добавления пакета в workspace/uv.lock.

## 11. PR lifecycle / commit / squash

### PR 1 — пример команд

См. `PR01_HANDOFF.ru.md` в ZIP. Предлагаемое разделение коммитов по файлам:

```powershell
git add portfolio/catalog/registry.json frontend/tsconfig.json frontend/app/portfolio/preferans/page.tsx portfolio/preferans/project.json portfolio/preferans/README.md portfolio/preferans/frontend portfolio/preferans/backend/README.md portfolio/preferans/tests
git commit -m "chore(preferans): register isolated portfolio module and guarded route"

git add portfolio/preferans/docs portfolio/preferans/SESSION_NOTES.md
git commit -m "docs(preferans): add architecture plan, rules and session handoff"
```

Перед первым commit рекомендуется обновить `SESSION_NOTES.md` с реальными выполненными проверками. Проверить `git show --stat` перед push.

```powershell
task ci
git push -u origin feat/preferans-foundation
gh pr create --base main --head feat/preferans-foundation --title "chore(preferans): bootstrap isolated protected portfolio module" --body-file "$bundle\PR01_BODY.md"
```

Если GitHub CLI недоступен, открыть PR в веб-интерфейсе и вставить текст из `PR01_HANDOFF.ru.md`. **Squash** после зелёного CI и проверки; не запускать squash локально поверх открытого PR без причины.

## 12. Критерии «готово» для всего проекта

- Реальная игра на трёх людях от регистрации комнаты до итоговой ведомости; все исторические виды контрактов, штрафов и помощи проверены fixture-тестами.
- Reconnect/restart у любого игрока не меняет руки, текущее право хода, журнал и ledger; нет дублей команд/штрафов.
- Браузер и прямой Render без доступа не видят игровые данные, чужие карты и управление; разработчик пробует атакующие запросы сознательно.
- Owner/Admin могут редактировать параметры наборов правил и корректировать **только активные** ledger; причины и аудит доступны всем трем, finished immutable.
- Статистика, рейтинг по золотым медалям, персональные графики и шуточные «голые» наказания имеют явную проверяемую арифметику.
- Голос/видео добровольны; локальная запись возможна после тройного согласия, прекращается при отзыве; поддерживаемые/неподдерживаемые браузеры перечислены.
- Вся пользовательская документация на русском, публичная карточка на английском; конфиденциальные данные, UID и ключи не публикуются.
- Нет новых paid services без отдельного согласия; честные ограничения бесплатной инфраструктуры описаны пользователю.
- Полный `task ci` и hosted smoke без регрессий существующих проектов.

## 13. Актуальные внешние основания

- [Render Free: spin-down и ephemeral filesystem](https://render.com/docs/free)
- [Render WebSockets 2026](https://render.com/changelog/free-web-services-now-remain-active-while-receiving-websocket-messages)
- [Firebase Firestore security rules and queries](https://firebase.google.com/docs/firestore/security/rules-query)
- [Firestore transactions / concurrency](https://firebase.google.com/docs/firestore/manage-data/transactions)
- [Firestore realtime listener billing](https://firebase.google.com/docs/firestore/pricing)
- [MDN Canvas.captureStream](https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/captureStream)
- [MDN MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/MediaRecorder)

**Примечание:** цены и квоты меняются; отсутствие дополнительной платы — текущий бюджетный критерий, а не гарантированное свойство облачного сервиса при любой нагрузке.


## PR 6 — implementation checkpoint after #272 (2026-11-23)

Branch `feat/preferans-game-controls` adds persisted counter, vote-based last-action undo, room-admin correction with appended events and a numeric pre-game policy. Test acceptance is `docs/PR06_UAT.ru.md`, algorithm details are `docs/PR06_GAME_CONTROLS.ru.md`. The nominal PR 6 plan above remains authoritative for previously specified requirements not yet implemented: historical ruleset editor, immediate offline detection and accidentally exposed card voting. These are explicitly still release gaps, not claims of completeness. PR 7–9 proceed in the order above.
