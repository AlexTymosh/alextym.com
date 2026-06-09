# Grafana Cloud logs

Проект может отправлять безопасные структурированные backend-логи в Grafana
Cloud Loki.

Backend сохраняет обычные JSON stdout logs для Render и может дополнительно
отправлять копию безопасных `WARNING` / `ERROR` событий в Loki через
ограниченную фоновую очередь.

## Архитектура

```text
FastAPI / structlog
  -> JSON stdout logs для Render
  -> safe Loki export queue
  -> background Loki push worker
  -> Grafana Cloud Loki
  -> Grafana Explore / log dashboard
```

Loki export специально сделан optional и fail-safe:

- выключен по умолчанию;
- не заменяет Render stdout logs;
- отправляет логи из фонового worker, а не прямо из request path;
- использует ограниченную очередь;
- отбрасывает логи, если очередь заполнена;
- не ломает приложение при ошибках Loki;
- экспортирует только allowlist безопасных структурированных полей.

## Render environment variables

Эти переменные нужно задавать только в Render, не в GitHub:

```env
LOG_EXPORT_ENABLED=true
LOG_EXPORT_MIN_LEVEL=WARNING
LOKI_PUSH_URL=<grafana-cloud-loki-push-url>
LOKI_USERNAME=<grafana-cloud-loki-username-or-instance-id>
LOKI_TOKEN=<grafana-cloud-access-policy-token-with-logs-write>
LOKI_QUEUE_MAX_SIZE=1000
LOKI_TIMEOUT_SECONDS=1.5
LOKI_BATCH_SIZE=50
LOKI_FLUSH_INTERVAL_SECONDS=2.0
```

Для временной smoke-проверки можно поставить:

```env
LOG_EXPORT_MIN_LEVEL=INFO
```

Потом сделать несколько запросов, убедиться, что логи появились в Grafana
Explore, и вернуть обратно:

```env
LOG_EXPORT_MIN_LEVEL=WARNING
```

## Настройка Grafana Cloud

1. Открой Grafana Cloud Portal.
2. Открой stack проекта.
3. Найди Logs / Loki connection details.
4. Скопируй Loki push URL.
5. Создай или используй Access Policy token с правом `logs:write`.
6. Добавь значения в Render environment variables.
7. Сделай redeploy backend service.

Не добавляй Loki credentials в `.env.example`, README с реальными значениями,
dashboard JSON, issue comments, screenshots или PR text.

## Проверка в Explore

Открой Grafana Cloud:

```text
Explore -> Loki datasource
```

Datasource обычно называется примерно так:

```text
grafanacloud-<stack-name>-logs
```

Базовый запрос:

```logql
{service="portfolio-backend"}
```

Production logs:

```logql
{service="portfolio-backend", environment="production"}
```

Warnings:

```logql
{service="portfolio-backend", environment="production", level="WARNING"}
```

Errors:

```logql
{service="portfolio-backend", environment="production", level="ERROR"}
```

Найти конкретный request:

```logql
{service="portfolio-backend"} | json | request_id="req_..."
```

Поиск по backend event:

```logql
{service="portfolio-backend"} | json | event="http.request.failed"
```

## Dashboard

Стартовый dashboard лежит здесь:

```text
infra/observability/grafana/dashboards/backend-logs.json
```

Импорт в Grafana Cloud:

```text
Dashboards -> New -> Import -> Upload dashboard JSON file
```

Когда Grafana спросит datasource, выбери Grafana Cloud Loki datasource.

Dashboard содержит:

- общее количество экспортированных логов;
- errors;
- warnings;
- logs by level;
- errors by event;
- recent errors;
- recent warnings;
- recent warning/error logs.

## Безопасные экспортируемые поля

Экспортировать нужно только безопасные structured fields:

```text
timestamp
level
service
service_version
environment
event
message
request_id
logger
method
route
status_code
status_class
duration_ms
error_type
```

Loki labels должны оставаться low-cardinality:

```text
service
environment
level
```

`request_id` специально остаётся внутри JSON log body, а не становится label.

## Что нельзя экспортировать

Не отправлять в Loki:

```text
raw user messages
contact form message bodies
names
emails
IP addresses
Authorization headers
cookies
API keys
tokens
raw prompts
request bodies
response bodies
full query strings
```

## Operational notes

- В production держи `LOG_EXPORT_MIN_LEVEL=WARNING`, если нет временного debug.
- `INFO` используй только для короткой smoke-проверки.
- Очередь должна оставаться ограниченной.
- Лучше потерять часть логов, чем замедлить или уронить backend.
- Logs объясняют причину проблемы; metrics и alerts остаются основным сигналом
  мониторинга.

## Полезные queries

Log volume по выбранному интервалу:

```logql
sum by (level) (
  count_over_time({service="portfolio-backend"}[$__interval])
)
```

Error count за выбранный range:

```logql
sum(count_over_time({service="portfolio-backend", level="ERROR"}[$__range]))
```

Top error events:

```logql
topk(10,
  sum by (event) (
    count_over_time({service="portfolio-backend", level="ERROR"} | json [$__range])
  )
)
```
