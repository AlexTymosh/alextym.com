# Zaporizhzhia Preferans — Modernization Development Plan

**ID:** PREF-MOD-PLAN-001 · **Версия:** 1.0 · **Дата:** 24.11.2026
**Базовый `main` при анализе:** `93611d3ea7c67a5762888c6ed17bd146406d7d4c`.
**Статус:** план и документы готовы к согласованию; программирование PR10 не начато.
**Нормативный документ:** [MODERNIZATION_TECHNICAL_SPECIFICATION.ru.md](MODERNIZATION_TECHNICAL_SPECIFICATION.ru.md), далее MOD-TZ.
**Проект:** `portfolio/preferans/`. Все пути ниже, кроме явно обозначенных host paths, относительно этой папки.

## 1. Стратегия доставки: пять PR, один контекст за раз

Не переписывать игру целиком. Сохранить действующий серверный движок, историю, scoring, Firebase auth и embedding в общем сайте. Сначала убрать архитектурный источник задержек и лишних расходов, затем построить новую сцену, перенести на неё действия, синхронизировать общие предметы и медиа, после чего провести полную приёмку. Все пять PR планируются как продолжение прежней нумерации этапов 1–9; реальные номера GitHub будут присвоены при создании PR. Существующий исправляющий PR или номер GitHub не обозначает номер этапа.

| Этап | Ветка | Доставка | Коммиты (ориентир) | Предшественник |
|---|---|---|---:|---|
| 10 | `feat/preferans-realtime` | Защищённый realtime, присутствие, паузы/таймеры, измеряемые расходы | 1 docs + 3 code/checkpoint | Актуальный main |
| 11 | `feat/preferans-game-table` | Макет, новый стол, колода, ротация мест, лобби | 2–3 | 10 merged |
| 12 | `feat/preferans-game-interaction` | Торговля, снос/ход, прикуп/взятка, сортировка, автораздача и анимации | 2–3 | 11 merged |
| 13 | `feat/preferans-shared-room` | Общие объекты, пулька/магнитофон, перерыв, медиа/запись и меню | 4 | 12 merged |
| 14 | `feat/preferans-modernization-release` | Приёмка, остаточные точечные исправления, 6/8h budget, release/rollback | 2–3 | 13 merged |

Всего ориентир **14–17 содержательных коммитов**, включая первоначальную фиксацию плана. Это не обязательная квота коммитов. Один коммит должен соответствовать проверяемому срезу, а не отдельному файлу, тесту или косметической правке. Не сохранять полурабочую миграцию в main. Squash merge каждого PR после hosted CI и Owner review. После merge начать следующую ветку от нового main; не продолжать с устаревшей feature branch. Не создавать отдельные PR только ради форматирования, документации или прототипа. При объективном крупном ранее неучтённом блокере — показать его Owner, согласовать перераспределение/отдельный PR; не добавлять silently.

### 1.1. Чёткая граница текущего поручения

Сейчас разрешены только три документа и инструкция их установки. **Остановиться после сохранения документов.** Не создавать backend/frontend код, ассеты, тесты продукта, менять Firebase/Render/Vercel, выполнять миграцию или запускать игровые операции. Ветка PR10 создаётся Owner локально, документы можно закоммитить одним docs-коммитом. Не открывать преждевременно пустой PR и не запускать разработку PR10 без отдельного распоряжения.

### 1.2. Протокол работы Codex и контекст

1. Перед началом этапа прочитать проектный `SESSION_NOTES.md`, этот план (только текущий PR), нужные параграфы MOD-TZ и исходного ТЗ, root `AGENTS.md`. Затем `git status`, branch, `git log`, `git diff`; проверить актуальный main и docs. Не доверять старому snapshot, если файлы изменились. Не загружать все прежние переписки и документы в контекст.
2. Кратко описать выбранный срез, существующие контракты, связанные тесты, ожидаемые paths. Сначала воспроизводящий тест/fixture и подтверждение текущей модели, затем минимальное исправление. Не изобретать API без чтения действующего router/store/client.
3. После каждого среза: пройти focused tests, обновить `SESSION_NOTES.md` коротким checkpoint (SHA/dirty state, что готово, что не проверено, следующая узкая задача, изменённые договорённости). Сохранять вывод проверок, но не огромные логи или секреты в заметке. Сверять статус по фактам. Если контекст исчерпан, остановиться в проверяемом состоянии, новый сеанс читает checkpoint.
4. До PR: проверить границы модулей, полный применимый CI, README/контракты/ADR, сохранность базового поведения. Owner выполняет коммиты, push, PR, squash merge; агент не делает git mutations, удалённые изменения, deploy/IAM/оплаты без прямого поручения. В финальном сообщении предоставить готовые PowerShell команды и английские PR/squash title/body.
5. Следующий этап только после подтверждения Owner о merge и отдельного распоряжения. При необходимости предыдущий PR имеет короткий post-merge UAT; новый флаг по умолчанию off, работающий старый интерфейс остаётся доступным. Не отключать активные production-флаги по старой документации.

**Формат checkpoint (замена короткого раздела, а не бесконечное накопление):**

```text
Current work package / branch / inspected base SHA:
Owner authorization / status:
Completed slice and affected paths:
Last tested commit / working-tree state:
Executed checks (exact commands and results):
Not executed, failures, risk and reproduction:
Decision or ADR refs:
Next smallest deliverable / explicit stop condition:
```

Корневой `SESSION_NOTES.md` принадлежит основному сайту и не изменяется. Проектный SESSION_NOTES — не CI/build contract: не проверять его hash, title или existence в CI/installer, не добавлять dependency от него в runtime. Старые исторические записи доступны из Git history; ссылки на HTTP 503 runbook и незакрытые риски сохраняются. Большие технические решения хранить в `docs/`, не в checkpoint.

## 2. PR10 — Realtime, Presence & Cost Optimization

**Ветка:** `feat/preferans-realtime`
**Цель:** существенно сократить задержку и лишние Firestore операции, сохранить возможность играть при сбоях транспорта. Никакого нового дизайна в этом PR.
**ТЗ:** MOD-TZ §§2,4–6,12–14; исходное ТЗ §§15,16,20,24.
**Предусловие:** Owner отдельно разрешил реализацию; чистая ветка от актуального main с первоначальным docs checkpoint.

### Срез 10.A — измеримый baseline, доменные инварианты и ADR

- Перечитать `online/store.py`, `views.py`, `router.py`, `controls`/timer modules по фактическому tree, клиент `room-client.ts`, `PreferansGame.ru.tsx`, текущие BFF, Firebase credentials/admission/grant path, host `AGENTS.md` и deployment docs. Подтвердить существующий SDK fix `ref.get(transaction=tx, timeout=5.0)` и отсутствие регрессий HTTP 503. Не предполагать рабочий production IAM на основании unit tests. Проверить процессы/worker count Render по доступной конфигурации, не менять их.
- Создать короткий ADR `docs/ADR_REALTIME_TRANSPORT.ru.md`: выбор Render WSS с одноразовым ticket и HTTP BFF commands, исключение прямого WSS из host architecture, config discovery, auth/revocation, bounded state, restart, multiple workers, rollback, измерение бесплатных квот. Разрешение на прямой WSS ограничено этим каналом и должно быть обосновано; при невозможности безопасного решения остановиться. Не использовать неподтверждённый платный broker или Vercel proxy на 6h.
- Измерить baseline на emulator/test fixtures: document reads/writes на create/join, 1 accepted action, repeated action, view unchanged/changed, pulse, media poll, history, settlement; разделить latency commit от client update. Не использовать production реальные комнаты для нагрузочного теста. Составить таблицу реального пути и целевые бюджеты. Проверить лимит Firestore shared daily quota, Render/Vercel plan, storage и traffic (Owner может предоставить usage); при отсутствии метрик явно «не проверено».
- Сформировать список gaps исходного ТЗ (`docs/MODERNIZATION_GAP_REGISTER.ru.md`, только действительно непокрытые требования с evidence file/test, PR owner и status). Обязательные кандидаты: room creation admin-only, first readiness/seat/rules, room list/archive, sheet discard/technical loss, punch substitution, ruleset editor, accidental reveal voting, stale timer edge cases, recording consent. Отдельно проверить старые открытые исторические случаи, не менять правила без подтверждения. Распределить работу по PR11–14, не откладывать все пробелы на финал.
- Ввести измерения без PII и без лишних Firestore writes; список performance metrics в ADR. Проверить, что обычный `pulse` сейчас меняет version/пишет события; сформулировать будущий тест, что heartbeat это больше не делает.

**Checkpoint A:** baseline report, ADR, gap register, точные test evidence. Согласовать предлагаемое исключение WSS и topology до B. В первом рабочем коммите допустимо совместить ADR, instrumentation и тесты; если это всего лишь документация без достаточной проверки, не маркировать транспорт реализованным.

### Срез 10.B — серверный realtime и безопасный lifecycle

- Изолированный hub/service/router внутри `backend/src/preferans/online/`; только минимальные host registration/BFF allowlist/config changes. Добавить short-lived one-use ticket bootstrap (origin allowlist, project/room/seat auth, replay/expiry/revocation), версионный протокол с bounded queue/message limits, targeted projection delivery. `View` и внешний Owner не получают скрытые данные. Не передавать token в URL или лог. Все значимые commands всё ещё проверяются текущим store/domain. Broadcast только после успешного commit; если возможно, строить per-seat snapshot из уже сохранённого результата, не три дополнительных Firestore read. Проверить несовместимость worker topology.
- Реализовать серверное presence + heartbeat без игрового event и write на каждый сигнал. Legacy `pulse` только fallback; on disconnect/resync pause, не полагаться на camera state. Базовый независимый `pause_reasons` и server freeze/resume/checkpoint для текущих timer/undo/future overlays; сохранить remaining, не начислять штрафы во время неизвестного offline. Не реализовывать UI пульки/магнитофона и готовности в этом срезе; подготовить ограниченные типы/переходы и тесты, в PR13 расширить. Сохранить transaction invariants, expected_version/idempotency, legacy docs default; рассмотреть отдельные versions/epoch в протоколе.
- Unit/contract/emulator tests: token replay/expiry, Origin, access denial, three distinct seats, cross-room, stale grant, invalid frames, slow client, commit failure (нет уведомления), retry/out-of-order, presence no writes, independent pause, timer boundary/restart. Реальные SDK tests для transaction and projection path. При синтетическом fake DB — явно отдельно emulator evidence.

**Checkpoint B:** безопасный transport adapter и presence/timer unit/contract tests. Старый HTTP клиент продолжает работать. Новые флаги default off. Нет функциональных изменений house rules.

### Срез 10.C — клиентская интеграция, fallback и оценка бюджета

- Типизированный realtime client/adapter: auth bootstrap, state/version/sequence handling, disconnect backoff+jitter, resync, bounded fallback polling; единый lifecycle, не два параллельных polling и WS. Обновить текущий интерфейс минимально: реальные per-seat status либо безопасное сообщение, не новый стол. Оптимизировать историю/рейтинг на lazy loading по мере внедрения меню (до PR11/13 можно остановить дублирующие запросы, не удалять возможность просмотра).
- Не включать постоянный Firestore media polling ускорением; подготовить контракт targeted messages для PR13, до его интеграции сохранять безопасную деградацию/feature gate. Не обещать NFR-08/09 с активным старым медиа polling; протестировать core отдельно, повторить end-to-end с медиа в PR13/14.
- 3 browser contexts или реальные emulator clients: create/join/start/trade/play/undo/reconnect, версии, частота reads/writes, latency p50/p95/p99, duplicate/restart, denied grants; test WS outage + HTTP fallback; graceful quota/503. Короткий 30–60min soak с ускоренным детерминированным timer test и бюджетной проекцией на 6h; не выдавать за фактический 6/8h тест. Убедиться, что no heartbeat writes при WS. Вывод метрик для Owner, оценка fallback и других сервисов; если p95/бюджет не соблюдены — объяснить/оптимизировать перед merge или сохранить feature disabled.
- Документация: protocol/auth, config/feature flags, runbook, baseline and post-change evidence; обновить `SESSION_NOTES.md`. Тесты существующего проекта и всего сайта. Продолжение PR11 после merge и подтверждения Owner.

**PR10 Definition of Done:** RT-01–RT-04 из MOD-TZ (для core, без будущего UI); реальные permissions/emulator, стабильные snapshots; durable commands; старые игры не сломаны; расходы измерены/ограничения явно названы; safe rollout/rollback; нет нового оплачиваемого ресурса. Не включать production realtime самовольно.

**Коммиты (пример после проверок):**

- `docs(preferans): 📝 define modernization scope and delivery` — уже подготовленные 3 документа; до реализации.
- `refactor(preferans): 📊 establish realtime cost baseline` — ADR, измерения, gaps, инварианты, тесты.
- `feat(preferans): 🔐 add authenticated realtime delivery` — backend/ticket/projections/presence/timer, tests.
- `feat(preferans): ⚡ add resilient realtime client` — integration/fallback/acceptance evidence + актуальные docs/notes.

Возможны другие краткие названия после просмотра реального diff. Проверить действующие repo commit conventions; title до 72 символов, body конкретный, на английском, без обещаний о непроверенном. Не делать `git add .`.

## 3. PR11 — Game Table & Classic Cards

**Ветка:** `feat/preferans-game-table`
**Цель:** визуальная архитектура настоящего стола и корректное положение игроков; никакой переписки правил.
**ТЗ:** §§3,7,12,14.
**Вход:** merged PR10, устойчивый client contract, RT findings; сформирован gap register.

### Срез 11.A — прототип, принятие дизайна и геометрия

- Сделать оригинальный локальный интерактивный прототип (изолированная demo fixture, без реальных room operations) для desktop и mobile landscape: lobby, 3 seats, auction, 12-card hand, open defenders, pause; показать Owner до реального UI merge. В PR11 не копировать старые скрины/цвета, не строить 3D. Учесть ограничения текущих CSS Modules и shared navbar.
- Один чистый mapping seat→left/right/bottom и inverse; turn/controller/winner/widow/score orientation; тесты всех трёх мест, не путать порядок серверного хода.
- Дизайн-система в рамках модуля: тёплый интерьер, ясный контраст, table surface, компактные кнопки, локальные SVG/ассеты; 32 уникальные карты с русскими индексами и традиционными фигурами + красноватая узорчатая рубашка. Лицензии/provenance/размер в `docs/ASSET_LICENSES.ru.md`. Не использовать реальные личные фото и неизвестные коммерческие сканы.

**Checkpoint A:** Owner подтвердил расположение (или согласованы корректировки); fixtures, mapping tests, ассеты с provenance. Без утверждения прототипа не выносить дизайн в production.

### Срез 11.B — защищённый стол и лобби

- Разделить монолит `PreferansGame.ru.tsx` на небольшие project-local компоненты: `Lobby`, `GameTable`, `Seat`, `Hand`, `TrickArea`, `TableObjects`, `ProjectSidebar` (названия предложены); game state controller остаётся единым, не дублировать legal actions/score. Использовать safe public view поля; opponent backs не содержат скрытых card IDs даже в DOM/ARIA. Разрешённые open hands и controller выделяются.
- Стол: руки соперников слева/справа, прикуп верх/центр, текущая взятка центр, свои карты снизу, место для панели решений над ними, компактные аватары/video slots, пулька и магнитофон пока как безопасные элементы/подготовленные точки расширения (не обещать готовую синхронизацию до PR13). Удалить длинную страницу из активной игры, не удалить функции: существующие панели переехать в доступное меню. Перенести историю/рейтинг в lazy sidebar; связь per-seat, ободок turn, accessible fallback. Ни одной новой игровой команды не отправлять исключительно из анимации.
- Lobby UX: список доступных комнат/продолжить игру, понятные invite/occupancy/start, имена/аватары из разрешённого существующего profile projection, нет UID/email; создание только уполномоченный admin. Проверить прежний режим Test/Admin. Первое readiness, правила/сдающий/места по исходному ТЗ; если изменение серверных workflows требует отдельной части, выполнить scoped в 11.C, не скрыть кнопки при сохранении доступного API.
- Responsive: desktop 1280×720+, mobile landscape, portrait prompt, сохранение reconnect/отзыва согласия; keyboard/touch, focus/contrast, safe-area, no overflow; video placeholders без включения камеры. Сохранить старые API/route/catalog/auth.

### Срез 11.C — визуальная и workflow регрессия

- E2E на 3 perspectives (включая 10/12 cards, открытую руку, lobby, turn/controller, ошибку доступа, reconnect), screenshot evidence только на synthetic fixtures. Mobile landscape interaction, portrait not lost state, reduced motion. Проверить общую portfolio карточку и существующие smoke tests, responsive main site; не исправлять чужой UX ради этого PR.
- Закрыть конкретные lobby/access gaps, обнаруженные в 10.A, с реальной проверкой прямого API. Не переписывать room lifecycle без необходимости. Актуализировать документы и checkpoint, полный CI.

**Коммиты:** `feat(preferans): 🃏 add classic cards and table geometry`; `feat(preferans): 🪑 build responsive private game table`; при необходимости `fix(preferans): 🚪 enforce lobby readiness and room roles`.
**DoD:** UI-01/02; место каждого однозначно; desktop/mobile, hidden-card tests; UI прототип принят Owner; working auction/play controls не потеряны; новых скрытых данных нет.

## 4. PR12 — Game Interaction & Deal Flow

**Ветка:** `feat/preferans-game-interaction`
**Цель:** перенести все действия в естественную игровую сцену, не менять формулы.
**ТЗ:** §§6.4,8,9.1 (только контракт публичных snapshot),12–14.

### Срез 12.A — торговля и стадии

- Отдельные фазовые панели из текущего server view: пас/число/масть/особые заявки, «Здесь [текущая ставка]» и запрет 6♠, второй клик отправляет ставку; показывать состояние возле аватара. Не включать неразрешённые server legal bids. Отдельно окончательный заказ после сноса, мизер вне обычного заказа, БП строго по исходному рангу. Проверить оборону, возврат виста, «Обязаловку», светлый/тёмный вист, мизер, «без трёх», публичные реплики и отмену ставки.
- Автоматическая следующая раздача через 5 секунд после settlement и всех обязательных решений: серверное ожидание, idempotent deal ID, pause/resume/restart, первая сдача ручная; final/archived не стартует. Тесты двойного scheduler и last-pool/bonus cases, старого клиента с ручной кнопкой. Не запускать auto-deal, если есть неподтверждённый расчёт.

### Срез 12.B — карты, прикуп, снос, взятки и анимации

- Визуально показать прикуп только в легальной фазе, потом скрыть; public replay data минимально необходимы, не раскрывать закрытый БП или второй passout card раньше времени. Контракт повторного показа/last trick подготовить для PR13, сам общий overlay подключить там. Снос отдельным действием, ход из разрешённых карт, поддержка touch/keyboard/drag. Не удалять действующее подтверждение хода карты без Owner approval. Взятки в 3 слоты, winner animation; распределение по 2, короткая анимация из server snapshot; no optimistic score/extra writes. Reconnect пропускает старые анимации, reduced motion.
- Сортировка: длина группы, старшая карта, стабильная масть, внутри по убыванию; personal persisted preference по UID, ручной порядок текущей сдачи, touch reorder/keyboard, не сбрасывать на каждом snapshot. Тесты 10/12 карт и изменения руки; не делать DB write на каждый drag.

### Срез 12.C — сценарии и оставшиеся игровые UX gaps

- Unit/Playwright 3 contexts: полный auction→declare→defense→play→settlement→auto-next; мизер/БП, passouts, открытые руки, 6♠, invalid action, stale version, undo/counter, network pause, correction, personal sort. Привязать golden scoring regression. Если обнаружена отсутствующая историческая операция (например согласованный исход мизера/случайное раскрытие), определить по gap register; реализовать только подтверждённое в рамках стадии, не изобретать исход. Не считать видимый UI доказательством выполнения серверного действия.
- Сохранить docs API contract и обновить `SESSION_NOTES.md`; CI и Owner review.

**Коммиты:** `feat(preferans): ♠️ add phase-aware bidding and contracts`; `feat(preferans): 🃏 improve hand and trick interactions`; при необходимости `feat(preferans): ⏱️ automate next deal after settlement`.
**DoD:** UI-03–05, повторные показы пока только подготовленный контракт/открытый data projection, auto-deal работает; сохранены правила и pending settlement; никаких неподтверждённых карт в HTML/WS/API. PR13 подключает общие overlays.

## 5. PR13 — Shared Room & Long-session Media

**Ветка:** `feat/preferans-shared-room`
**Цель:** единое пространство комнаты, не только персональный экран. Пулька, прикуп/last trick, перерыв, музыка и добровольная связь/запись.
**ТЗ:** §§6,9–12,14.
**Предусловие:** server pause/transport из PR10, scene and actions из PR11/12. Это самый объёмный этап, поэтому четыре самостоятельных среза; остановка после каждого проверенного коммита и handoff, не требовать удерживать код всех четырёх срезов в одном сеансе.

### Срез 13.A — общее presentation state и паузы

- Отдельная версия публичного `RoomPresentation`, один overlay, open/close от любого сидящего, initiator visible, atomic replace, concurrent actions, reconnect; pause reasons проверяются сервером. При last trick следующий допустимый ход атомарно closes+plays, другие причины блокируют; invalid action не снимает overlay. Повтор прикупа только разрешённые ранее раскрытые карты. Shared break, готовность всех троих (2 недостаточно), независимые причины паузы; timer/counter/next-deal/undo freeze semantics. Durable pause transitions без writes per UI frame. Существующий WebSocket канал, не второй realtime polling.
- Тесты параллельных open/close, disconnect при overlay, ready/reset, timer remaining, разрешения/hidden data, legacy room, restart. Проверить новый/старый клиент и feature gate.

### Срез 13.B — пулька, меню и связанные workflows

- Оригинальный листок в клетку с тремя секторами, направлениями вистов и целью в центре; точная ориентация 3 places, цифры из ledger, доступная таблица, администратор preview/correction + reason/audit. Не придумывать отсутствующие исторические entries. Ленивая история/рейтинг и graph, колонки полученных/нанесённых наказаний, immutable result. Правила/FAQ, личные настройки, перерыв, бюджет/статусы.
- Закрыть связанные gaps по согласованному исходному ТЗ: sheet-discard workflow, выбор наказаний и полноценные parameter-only versioned rulesets, если текущие доказательства подтверждают отсутствие. Делать детерминированные server actions и golden tests, не переносить весь домен. Не записывать новые фактические наказания дважды; не переписывать прошлые результаты. Если объём окажется больше допустимого, остановиться на checkpoint, согласовать распределение с Owner до продолжения; не объявлять готовой функцию, которую UI только имитирует.

### Срез 13.C — общий магнитофон и разрешённое аудио

- Оригинальный локальный визуальный asset; UI увеличения с общей паузой, close любым/по столу, доступные controls. Music state как timestamped desired state, local play/pause/next/prev, reconnect position, drift, autoplay, local volume/mute. Синхронизируются команды, а не звук через сервер. Лицензированный manifest, тестовые разрешённые звуки; коммерческие композиции не поставляются без прав. Тесты sync, no unnecessary Firestore writes, disconnect, mobile gesture, volume private, музыка продолжает играть после закрытия и во время pause.

### Срез 13.D — перенос медиа на realtime и запись на диск

- Переиспользовать WebRTC mesh, auth, consent state; перенести SDP/ICE на targeted WS, удалить постоянный Firestore media polling из healthy path. P2P без платного TURN; fallback ограничен, при failure игра остаётся доступной. Cameras у соответствующих seats. Разрешения и mic/camera independent; не запускать автоматически. Защищённый consent, stop/watchdog/offline/revoke, restart/reconnect только с подтверждённым прежним контекстом, отсутствие hidden cards в canvas/audio. Включение записи по-прежнему gate.
- File System Access direct sequential writable stream, feature detection, chunk/backpressure limit, independently playable fallback segments, bounded RAM, disk failure graceful stop. Никакой загрузки файла на server. Тесты consent/recording adapter/writer failure/synthetic chunk sequence and queue, replay, all three sources; короткая реальная запись на поддерживаемом браузере. Полный 6h soak в PR14. Обновить docs фактических браузеров, прав, privacy и эксплуатационных ограничений. Старые Firestore signalling docs не удалять автоматически; ручная cleanup с лимитами и project confirm из PR9.

**Коммиты:** `feat(preferans): 🤝 synchronize shared room pauses`; `feat(preferans): 📒 add interactive score sheet and room menu`; `feat(preferans): 📻 synchronize local music playback`; `feat(preferans): 🎥 stream consensual recordings to disk`. Включить relevant tests/docs в соответствующие commits; отдельный docs-only PR не нужен.
**DoD:** SH-01–04, AV-01–03 на уровне автоматических сценариев и короткой проверки реальных устройств, оставшиеся длительные проверки в PR14. Core не зависит от медиа; consent/watchdog и private projection не ослаблены; бюджетная проекция с media теперь измерена; запись остаётся отключённой при невыполненной privacy gate.

## 6. PR14 — Acceptance, Hardening & Release

**Ветка:** `feat/preferans-modernization-release`
**Цель:** доказать корректность и бесплатную эксплуатацию долгой встречи, а не ещё раз переписать интерфейс.
**ТЗ:** §§4,12–14 и исходное ТЗ по всем оставшимся gap IDs.

### Срез 14.A — полная функциональная и security приёмка

- Взять актуальный gap register, закрыть только scoped defects; по крупным незакрытым сценариям Owner решает перераспределение, не менять статус без evidence. Сверить все согласованные house rules, включая крайние расчёты, zero-sum, pool overflow, passout rewards, conso, tie, technical loss, optional punch choice, исправления и историю. Реальные Auth/Firestore Emulator: no-access/View/Test/Admin/Owner, three seats, direct backend/WSS, expired grant, cross-room, hidden card data, duplicate requests, incorrect origin, rollback, SDK 503 path, old room schema and reconnect. E2E full game, multi-browser contexts, mobile landscape, keyboard/reduced motion.
- Проверить hosted portfolio/card/noindex/guests, other projects boundaries, root site, existing CI/CodeQL. Тесты не отключать и не маскировать таймаутами. Перед внесением исправлений доказать воспроизведение. Оставить миграции аддитивными. Документировать каждое отличие от baseline.

### Срез 14.B — измерения 6/8 часов и реальные устройства

- Отдельный воспроизводимый нагрузочный сценарий (не обычный CI): 3 независимых клиентов, 6h normal session и 8h reserve soak; как минимум сценарий с частыми действиями, паузами, reconnect, fallback, cold/restart, history access, audio commands, media signalling/recording where safe. Быстрые deterministic simulation tests не заменяют real-duration run. Вычислить rates и полный расход, измерить SDK/emulator counters, latency p50/p95/p99, memory/CPU/traffic, write/read retry, queue bounds, no-event heartbeat, quota reserve. Сверить с actual provider usage при отдельно разрешённом staging/Owner run; не проводить массовый production load без разрешения. Не включать billing для теста. Если бюджет выше, сначала оптимизировать и повторить; отсутствие данных = не пройдено.
- 3 реальных устройства минимум 2 сети, audio/video each pair, no-camera fallback, revoke/loss, 6h recording direct disk/segmented fallback, воспроизводимые файлы, RAM stable, disk errors. Измерить remote consent-stop latency, зафиксировать ограничения. Если P2P невозможно на сети, честно указать деградацию. Указать проверенные browser versions и unsupported modes. Никакого платного TURN/relay. В реальной приёмке Owner/друзья — добровольно, не публиковать записи/закрытые карты, тестовые материалы/снимки обезличены.

### Срез 14.C — release gate, runbook, финальный checkpoint

- Документы `docs/MODERNIZATION_UAT.ru.md` и `docs/MODERNIZATION_RELEASE.ru.md`: actual environment/commit, tests PASS/FAIL/SKIPPED, quota evidence, known issues, feature flags/migration/rollback, per-role access, retention/cleanup, supported browsers, limitations. Разделить core acceptance и optional media; не объявлять полное выполнение при отключённом обязательном сценарии. Указать fallback и отдельное разрешение Owner на deployment и production gates. Откат выключает новые gates и сохраняет durable results; если старый client несовместим с новой pause state, сначала безопасно завершить/заморозить, затем откатить по runbook.
- `task ci` и все actual hosted checks, Owner review, финальные README/SESSION_NOTES; no secrets/private info. Только после explicit Owner release approval изменить конфигурацию/включить новые функции. Если gate fail — candidate, не «готово». Сохранить историю PR и immutable results.

**Коммиты:** `test(preferans): 🧪 verify multiplayer and access invariants`; `fix(preferans): 🛡️ resolve measured release regressions` (только если нужны реальные исправления); `docs(preferans): 📋 record acceptance and rollout evidence`.
**DoD:** FIN-01–03; 6h budget and 8h stability evidence; privacy/auth intact, core and media separately marked; no paid plan; Owner-approved production activation. Если реальная 6/8h приёмка ещё не проведена, статус остаётся release candidate, тесты/PR могут быть зелёными, но не обещать готовность.

## 7. Проверки и handoff на каждом PR

| Стадия | Действие | Не допускается |
|---|---|---|
| Перед кодом | Read scope, status/log, актуальные contracts, current test suite, Owner authorization | Работа по старому SHA вслепую; скачивание предыдущего synthetic fixture вместо main |
| После среза | Focused pytest/TypeScript/Playwright/fixture, format, whitespace, test outcome | Умолчать FAIL/SKIPPED; заменить реальные integration tests fake DB |
| Перед PR | `task repo:check`, `task backend:check`, `task frontend:check`, `task ci` по Taskfile, relevant emulator, review git diff | `git add .`, глобальное отключение checks, unconditional production deploy |
| Hosted | Все реальные GitHub jobs, CodeQL при наличии, точный head SHA | Считать любой зелёный старый run доказательством нового PR |
| После squash | Обновить main; проверить merge SHA/CI, актуальный checkpoint; короткий post-merge smoke с Owner | Новый PR от старой ветки, force-push, rewrite history |

Точные команды для реализации/проверки/коммитов выдаются после каждого этапа на основании фактического diff и Taskfile. При прежних нестабильных тестах сначала проверить trace/error-context и воспроизвести точный сценарий, не менять таймауты вслепую. Документация — только актуальная, без новой дублирующей системы правил. План может уточняться с Owner, неизменяемое правило — не расширять scope без явного согласия.

## 8. Операционные решения, ещё не подтверждённые измерениями

- Прямой Render WSS с одноразовым ticket: согласованный выбор архитектуры; точная реализация и worker topology проверяются на PR10. Старые BFF API остаются.
- Показ прикупа трактуется как ещё один общий увеличенный объект с паузой; одновременно открытые objects заменяются атомарно. Это инженерные defaults MOD-TZ, не новые исторические правила; при прототипе Owner может уточнить.
- Нулевая стоимость и 500 ms — цели, не доказанные характеристики; текущая общая provider usage и IAM неизвестны в полной мере. Managed TTL, новые paid services и production changes запрещены без разрешения.
- Возможности браузеров и лицензии музыки/колоды требуют проверки; запись при потере связи fail-closed, а не обещание бесшовного файла при любом сбое. Не повторять ранее закрытые вопросы.

**Следующее действие Owner:** создать `feat/preferans-realtime`, сохранить документы из ZIP, проверить diff, при желании сделать один docs commit. Затем отдельной командой разрешить реализацию PR10. До этого не начинать программирование.
