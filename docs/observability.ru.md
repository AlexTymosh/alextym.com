# Observability, metrics и Grafana

Этот документ описывает текущий observability setup для portfolio web product
после этапов logging, metrics, local Grafana и Grafana Cloud.

## Scope

Observability слой намеренно сделан практичным и низкобюджетным:

- structured JSON logs для backend request и application events;
- request correlation через `request_id` и `X-Request-ID`;
- Prometheus-compatible HTTP и domain metrics;
- protected `/internal/metrics` endpoint;
- local Prometheus/Grafana lab для разработки;
- Grafana Cloud scrape protected production metrics endpoint;
- privacy-safe aggregate product metrics.

OpenTelemetry, traces, Loki и log shipping на этом этапе намеренно не
добавлены.

## Logging foundation

Backend использует structured logging, чтобы поведение request-ов было проще
анализировать локально и на hosting.

Log records содержат стабильные operational fields:

- timestamp;
- level;
- service;
- service version;
- environment;
- logger name;
- request ID, если он есть;
- route, status class и duration для HTTP request logs.

Request correlation выполняется через request-context middleware. Если visitor
передал валидный `X-Request-ID`, backend переиспользует его. Иначе backend
создаёт новый ID и возвращает его в response header.

Logs не должны содержать query strings, personal messages, tokens или
secret-like values.

## Metrics foundation

Backend отдаёт Prometheus-compatible metrics только через protected internal
endpoint:

```text
GET /internal/metrics
Authorization: Bearer <METRICS_TOKEN>
```

Metrics выключены по умолчанию:

```env
METRICS_ENABLED="false"
METRICS_TOKEN=""
METRICS_PATH="/internal/metrics"
```

В production нужен длинный random token. Local development token нельзя
использовать в production.

## Группы метрик

### HTTP metrics

Создаются FastAPI instrumentation layer:

- request count;
- request duration histogram;
- request и response size metrics;
- route/handler labels;
- method и status labels.

Route labels должны быть templated и low-cardinality. Raw dynamic values, query
strings и private values не должны попадать в metric labels.

### Domain metrics

Domain metrics описывают поведение продукта:

- `portfolio_chat_requests_total`;
- `portfolio_chat_responses_total`;
- `portfolio_chat_policy_decisions_total`;
- `portfolio_rag_retrievals_total`;
- `portfolio_rag_retrieval_duration_seconds`;
- `portfolio_rag_retrieved_chunks`;
- `portfolio_llm_requests_total`;
- `portfolio_llm_request_duration_seconds`;
- `portfolio_contact_submissions_total`;
- `portfolio_escalation_events_total`;
- `portfolio_rate_limit_checks_total`.

Эти метрики нужны для dashboards и alerts, а не для хранения private
conversation content.

### Privacy-safe product metrics

Product metrics являются только агрегированными:

- `portfolio_page_views_total{page="..."}`;
- `portfolio_resume_downloads_total{source="resume_page"}`.

Frontend отправляет только whitelisted event values. Backend валидирует их до
увеличения метрик.

Проект не собирает:

- visitor IDs;
- user IDs;
- cookies для analytics;
- localStorage tracking IDs;
- IP hashes;
- User-Agent hashes;
- raw referrers;
- query strings;
- per-user chat usage.

## Local observability lab

Local lab находится здесь:

```text
infra/observability/
```

Внутри:

- Prometheus Docker Compose service;
- Grafana OSS Docker Compose service;
- Prometheus scrape config;
- Grafana datasource provisioning;
- Grafana dashboard JSON.

Полезные команды:

```bash
task obs:config
task obs:up
task obs:logs
task obs:restart
task obs:down
```

Local access:

```text
Prometheus: http://localhost:9090
Grafana:    http://localhost:3001
```

Для local backend metrics нужно:

```env
METRICS_ENABLED="true"
METRICS_TOKEN="local-dev-metrics-token"
METRICS_PATH="/internal/metrics"
```

## Grafana Cloud setup

Production monitoring использует Grafana Cloud Metrics Endpoint scraping:

```text
Render backend /internal/metrics
  <- Grafana Cloud Metrics Endpoint scrape
Grafana Cloud dashboards
```

Production Render environment variables:

```env
METRICS_ENABLED="true"
METRICS_PATH="/internal/metrics"
METRICS_TOKEN="<long-random-secret>"
```

Рекомендованные настройки Grafana Cloud для low traffic:

```text
Job name: portfolio-backend
URL: https://<backend-host>/internal/metrics
Authentication: Bearer token
Scrape interval: 300s
```

Нельзя хранить `METRICS_TOKEN` в GitHub, dashboard JSON или документации.

## Dashboard

Dashboard находится здесь:

```text
infra/observability/grafana/dashboards/portfolio-observability.json
```

Он настроен под low traffic:

- default time range: last 14 days;
- slower refresh interval;
- weekly summary stat panels;
- daily count charts вместо tiny per-second rates;
- low-scale Y axes для редких events, например CV downloads.

Основные dashboard sections:

- backend scrape status;
- HTTP requests и HTTP 5xx;
- HTTP latency;
- chat requests и chat policy decisions;
- RAG retrieval latency;
- LLM request outcomes;
- contact и escalation events;
- rate-limit checks;
- page views;
- resume downloads.

## Возможные alerts

На этом этапе alert candidates документируются, но не обязаны быть committed as
code.

Первые полезные alerts:

1. Backend metrics scrape is down.
2. HTTP 5xx errors detected.
3. LLM/RAG failures detected.
4. Excessive rate-limit events, если появится spam.

Alerts должны быть редкими и actionable. Для low-traffic personal portfolio не
нужен большой alerting setup.

## Operational checks

Перед deployment:

```bash
task backend:check
task frontend:check
task rag:check
task ci:quick
```

Перед изменением observability files:

```bash
task obs:config
```

Manual production checks:

```bash
curl https://<backend-host>/internal/metrics
```

Ожидаемо без token: forbidden.

```bash
curl https://<backend-host>/internal/metrics \
  -H "Authorization: Bearer <METRICS_TOKEN>"
```

Ожидаемо с token: Prometheus text output.
