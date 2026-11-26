# PR22. Восстановление квоты Firestore и realtime

Дата расследования: 25.11.2026. Базовый коммит: `261b50e06dbf1ac7da81ba3781859f163638d307`.

## 1. Подтверждённые факты

- В production-логах Vercel на `/settings` — `8 RESOURCE_EXHAUSTED: Quota exceeded`.
- Vercel и Render успешно развернули один коммит. Рост чтений начался до его слияния.
- Firebase Usage за скользящие 24 часа: приблизительно 54 000 чтений, 8 200 записей. Это не точный счётчик бесплатного дня; проверять фактическую квоту в Google Cloud.
- В списке переменных Vercel не было `PREFERANS_REALTIME_ENABLED` и `NEXT_PUBLIC_PREFERANS_REALTIME_ENABLED`; скрытых production-переменных в результате проверки не было.
- Значения Firebase Project ID для Preview и Production совпадали. Render Dev ещё требуется проверить отдельно.
- Значения секретов, ключи сервисных аккаунтов и токены в отчёт не включены.

## 2. Решение и границы

Существующий single-worker WebSocket доставляет только авторизованные проекции конкретного места. Не внедряем вторую базу, Redis, новый тариф или новый процесс. Firestore остаётся источником истины, HTTP — каналом команд; проверки допуска и гранта выполняются как прежде в BFF и backend. Права не кешируются между запросами.

Изменения PR22:

- Резервный опрос: 15 с активная игра, 30 с прочие активные состояния, 60 с закрытая комната/скрытая вкладка. После получения архивированного состояния опрос прекращается. При ошибках 30–120 с и общий локальный cooldown по HTTP Retry-After. Heartbeat не запускается параллельно с предыдущим heartbeat и не обращается к сети во время cooldown. Режим degraded не выдаётся за realtime.
- Серверный circuit breaker открывается при подтверждённом RESOURCE_EXHAUSTED, 120/240/480/600 с. Обычные 401/403/409 не являются квотной ошибкой. В ответе 503 и числовой Retry-After, без приватной информации. Состояние ограничителя локально процессу: перезапуск его сбрасывает, он не заменяет лимиты провайдера и не гарантирует единственный глобальный пробный запрос. Уже начатые операции не отменяются. При отсутствии точной ошибки обычный backoff остаётся на клиенте.
- При неудачной сверке realtime следующий запуск не раньше 5 с. При квотной ошибке сверка и WS прекращаются до разрешения circuit; прежний механизм консервативного восстановления таймеров остаётся.
- Защита распространяется на чтения identity/profile/grant в frontend и защищённые игровые операции в backend; прочие Firebase API/SDK могут иметь собственные ретраи. RAG и его хранилища не изменены.
- `/settings` при ошибке сервиса показывает сообщение о временной недоступности, не выдаёт доступ по неподтверждённой сессии. Не удаляет cookie. Нет автоматического обновления страницы.

## 3. Оценка расходов (не измерение)

Для 3 клиентов, один из которых Owner с password-провайдером: до 11 чтений на один совместный неизменившийся HTTP poll (1 + 5 + 5). При изменённой версии и других провайдерах больше. 4 с — около 9 900 чтений/час только poll, 15 с — около 2 640; скрытая вкладка с 60 с — 660 для трёх скрытых клиентов. При здоровом WebSocket периодические `/view` и `/commands` pulse исчезают. Reauth (60 с) включает backend-проверки и room read; для одного password Owner + двух участников — около 420 чтений/час на стабильных версиях (1 + 3 + 3), плюс реальные действия, sync, retries, reconnect и остальные функции сайта. Отдельно: 1 760 обычных команд за 6 ч дают минимум 5 280 чтений и 7 040 записей транзакций; до 4 дополнительных auth reads на команду обычного участника. Поэтому 12 000 чтений за 8 ч не гарантированы; основной выигрыш — убрать холостой опрос, а не исключить все чтения.

Текущие метрики `GET /api/preferans/realtime-metrics` (Owner, same-origin) — только оценки процесса, включая `quota_trips`, `quota_blocked`, `quota_retry_after_s`. Не считать их точным биллинговым счётчиком. Во время открытого circuit endpoint также может быть недоступен.

## 4. Безопасное включение production (вручную после CI)

1. Закрыть активные игровые вкладки. Проверить Spark, отсутствие billing upgrade и фактический остаток квоты. Дождаться восстановления (сброс примерно в полночь Pacific; 26.11.2026 около 08:00 GMT). Не удалять комнаты и не сбрасывать пользователей.
2. Слить PR после полного CI, убедиться в зелёном деплое обоих компонентов одного SHA.
3. Render → **alextym-backend** (не portfolio-lab-dev) → Environment: добавить/проверить `PREFERANS_REALTIME_ENABLED=true`, `PREFERANS_REALTIME_SINGLE_WORKER=true`, `PREFERANS_REALTIME_ORIGINS=https://alextym.com`, `WEB_CONCURRENCY=1`. Сохранить существующие `PORTFOLIO_LAB_ENABLED=true`, `PREFERANS_ROOMS_ENABLED=true`. Проверить одну instance/worker. Добавлять www-origin только если домен действительно обслуживается и используется; не использовать wildcard. Не менять остальные переменные, ключи, billing, media flags. Save and deploy.
4. Vercel → **alextym-com** → Settings → Environment Variables: создать только для Production `PREFERANS_REALTIME_ENABLED=true` и `NEXT_PUBLIC_PREFERANS_REALTIME_ENABLED=true`. Не добавлять в Preview до разделения Firebase. Сохранить существующий `BACKEND_ORIGIN` и конфигурацию Firebase. Redeploy Production (публичная переменная встраивается на этапе сборки). Не копировать секреты в репозиторий.
5. Открыть комнату тремя отдельными авторизованными аккаунтами, DevTools Network → WS: соединение к `wss://alextym-backend.onrender.com/api/preferans/rooms/.../realtime`, HTTP 101, snapshot/ping/pong. Проверить надпись «Обновление в реальном времени» у каждого. Не публиковать ticket, cookie, содержимое snapshot или данные чужих рук.
6. DevTools Network → Fetch/XHR: спустя bootstrap нет постоянных `view` и HTTP `pulse`; остаются реальные команды, возможный единичный recovery view, проверки профиля/других функций. Закрытие WS должно переключать на ограниченный fallback; после восстановления — обратно на WS. Проверить revoke, перезапуск Render, таймеры и сохранённые комнаты без начисления из неизвестного интервала.
7. Если WS не работает: проверить status ticket (404 = flags; 403 = origin/роль; 503 = backend/quota), Console CSP, версию деплоя, точный URL Render, auth/seat. Не ослаблять CSP или доступы. Не запускать длительную игру в fallback до проверки бюджета.

## 5. Разделение Preview/Production

Существующую базу, в которой находятся реальные профили, grants, комнаты и результаты, оставить production; название проекта не является основанием менять ID. Для нового dev/preview использовать Firebase Emulator локально и, при необходимости, отдельный Spark-проект с отдельными тестовыми пользователями, проектными grants и правилами из `infra/firebase/firestore.rules`. Не копировать production аккаунты, приватные руки или service account credentials. Проверить `FIREBASE_PROJECT_ID` == `NEXT_PUBLIC_FIREBASE_PROJECT_ID` внутри каждой среды; Firebase server credential и публичная конфигурация должны относиться к этому же проекту. Render dev backend должен использовать отдельную dev конфигурацию, Preview BACKEND_ORIGIN — dev backend. Vercel Production и Render production должны совпадать между собой. До готовности отдельной среды отключить доступ к Lab в Preview (только Preview), не меняя Production. Изменение существующего Firebase Project ID без переноса auth/identity/grants нарушит вход; автоматической миграции нет.

## 6. Контроль бесплатного тарифа и критерии допуска

- Firestore Standard free: 50k reads / 20k writes / 20k deletes в день, 1 GiB хранения; проверять фактический счётчик и текущий тариф. Usage — приближённые данные. Проверять также Render free instance hours и outbound bandwidth, Vercel invocation limits. WS-сообщения Render являются входящим трафиком и поддерживают сервис активным; исходящие сообщения расходуют bandwidth. Не добавлять keepalive cron и не активировать платные метрики.
- Пороги ручного контроля всех потребителей: reads 35k/42.5k/47.5k и writes 14k/17k/19k (70/85/95%). При 85% не начинать новую длительную сессию; при 95% остановить нагрузочные тесты, закрыть вкладки. Cloud Monitoring / Metrics Explorer использовать только в рамках подтверждённого бесплатного тарифа; автоматические платные alerts/billing не включать. По возможности зафиксировать project-wide usage до и после теста и проверить квоту в Cloud Console.
- Пробный 15–30 минутный прогон (три клиента), затем 1 час; сравнить with previous 7–9k reads/h. На 6/8 ч перейти только после измерения запаса и успешной проверки безопасности. Цель PR14 6 ч <=15k reads /10k writes остаётся целевым бюджетом, не гарантия. Если активные команды доминируют, отдельным решением после профилирования рассмотреть перенос единственной авторитетной проверки доступа на backend с тестами всей границы доверия; не кешировать разрешения вслепую.
- Фиксировать baseline, duration, actions, auth mode, WS reconnect, fallback requests, reads/writes delta, other site traffic, actual p95 commit-to-render (>=100 measurements), error count and billing plan. Не считать 75 ms внутреннего цикла p95. Не использовать реальные персональные данные в тестовом отчёте.

## 7. Rollback

Не сбрасывать Firestore. Если конфигурационный запуск WS неуспешен, отключить оба Vercel realtime-флага и соответствующий Render-флаг после безопасной остановки игры, затем согласованно redeploy. Fallback PR22 остаётся замедленным; следить за квотой. При кодовой регрессии revert PR, не возвращать старый быстрый polling на длительное время без контроля. Не включать billing для обхода проблемы.

## 8. Источники

- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/firestore/monitor-usage
- https://firebase.google.com/docs/projects/billing/firebase-pricing-plans
- https://render.com/docs/free
- https://render.com/docs/websocket
- https://render.com/changelog/free-web-services-now-remain-active-while-receiving-websocket-messages

## 9. Ограничения пакета

Полный checkout GitHub недоступен в среде автора пакета. Точные anchors проверены по GitHub API, изолированные Python/TypeScript проверки выполнены. Полный CI, реальные deployment flags, Firebase Emulator и фактический production-тест не выполнены. Не отмечать эти этапы как пройденные до проверки.
