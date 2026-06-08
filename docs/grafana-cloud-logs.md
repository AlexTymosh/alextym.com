# Grafana Cloud logs

This project can export safe structured backend logs to Grafana Cloud Loki.

The backend keeps normal JSON stdout logs for Render and can optionally send a
copy of safe `WARNING` / `ERROR` events to Loki through a bounded background
export queue.

## Architecture

```text
FastAPI / structlog
  -> JSON stdout logs for Render
  -> safe Loki export queue
  -> background Loki push worker
  -> Grafana Cloud Loki
  -> Grafana Explore / log dashboard
```

The Loki export is deliberately optional and fail-safe:

- disabled by default;
- does not replace Render stdout logs;
- sends logs from a background worker, not directly from the request path;
- uses a bounded queue;
- drops logs if the queue is full;
- treats Loki failures as non-fatal;
- exports only an allowlist of safe structured fields.

## Render environment variables

Set these variables only in Render, not in GitHub:

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

For a temporary smoke test you can set:

```env
LOG_EXPORT_MIN_LEVEL=INFO
```

Then make several requests, confirm that logs arrive in Grafana Explore, and set
it back to:

```env
LOG_EXPORT_MIN_LEVEL=WARNING
```

## Grafana Cloud setup

1. Open Grafana Cloud Portal.
2. Open the project stack.
3. Go to the Logs / Loki connection details.
4. Copy the Loki push URL.
5. Create or reuse an Access Policy token with `logs:write` permission.
6. Add the values to Render environment variables.
7. Redeploy the backend service.

Do not put Loki credentials into `.env.example`, README examples with real
values, dashboard JSON, issue comments, screenshots, or PR text.

## Verify in Explore

Open Grafana Cloud:

```text
Explore -> Loki datasource
```

The datasource is usually named like:

```text
grafanacloud-<stack-name>-logs
```

Basic query:

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

Find a specific request:

```logql
{service="portfolio-backend"} | json | request_id="req_..."
```

Search by backend event:

```logql
{service="portfolio-backend"} | json | event="http.request.failed"
```

## Dashboard

A starter dashboard is stored at:

```text
infra/observability/grafana/dashboards/backend-logs.json
```

Import it in Grafana Cloud:

```text
Dashboards -> New -> Import -> Upload dashboard JSON file
```

When Grafana asks for a datasource, select the Grafana Cloud Loki datasource.

The dashboard includes:

- total exported logs;
- errors;
- warnings;
- logs by level;
- errors by event;
- recent errors;
- recent warnings;
- recent warning/error logs.

## Safe exported fields

Only safe structured fields should be exported:

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

Loki labels should stay low-cardinality:

```text
service
environment
level
```

`request_id` is intentionally kept in the JSON log body, not in labels.

## Do not export

Do not send these values to Loki:

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

- Keep `LOG_EXPORT_MIN_LEVEL=WARNING` in production unless you are temporarily
  debugging.
- Use `INFO` only for short smoke tests.
- Keep the queue bounded.
- Dropping logs is better than slowing down or crashing the backend.
- Loki logs explain incidents; metrics and alerts should still be the primary
  signal for monitoring.

## Useful queries

Log volume over selected interval:

```logql
sum by (level) (
  count_over_time({service="portfolio-backend"}[$__interval])
)
```

Error count over selected range:

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
