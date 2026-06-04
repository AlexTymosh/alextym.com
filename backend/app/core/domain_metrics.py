from __future__ import annotations

from time import perf_counter

from prometheus_client import CollectorRegistry, Counter, Histogram

DOMAIN_METRICS_REGISTRY = CollectorRegistry(auto_describe=True)

LATENCY_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)
CHUNK_COUNT_BUCKETS = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
SAFE_PAGE_LABELS = {"/", "/resume", "/chat", "/contact"}
SAFE_RESUME_DOWNLOAD_SOURCES = {"resume_page"}

CHAT_REQUESTS_TOTAL = Counter(
    "portfolio_chat_requests_total",
    "Chat requests completed by mode, outcome, and policy intent.",
    ("mode", "outcome", "policy_intent"),
    registry=DOMAIN_METRICS_REGISTRY,
)
CHAT_RESPONSES_TOTAL = Counter(
    "portfolio_chat_responses_total",
    "Chat responses completed by user-visible quality signals.",
    ("mode", "confidence", "not_enough_data", "handoff_suggested"),
    registry=DOMAIN_METRICS_REGISTRY,
)
CHAT_POLICY_DECISIONS_TOTAL = Counter(
    "portfolio_chat_policy_decisions_total",
    "Chat policy decisions by stable policy intent.",
    ("intent",),
    registry=DOMAIN_METRICS_REGISTRY,
)
RAG_RETRIEVALS_TOTAL = Counter(
    "portfolio_rag_retrievals_total",
    "RAG retrieval attempts by outcome.",
    ("outcome",),
    registry=DOMAIN_METRICS_REGISTRY,
)
RAG_RETRIEVAL_DURATION_SECONDS = Histogram(
    "portfolio_rag_retrieval_duration_seconds",
    "RAG retrieval latency in seconds by outcome.",
    ("outcome",),
    buckets=LATENCY_BUCKETS,
    registry=DOMAIN_METRICS_REGISTRY,
)
RAG_RETRIEVED_CHUNKS = Histogram(
    "portfolio_rag_retrieved_chunks",
    "RAG chunks returned per retrieval attempt.",
    buckets=CHUNK_COUNT_BUCKETS,
    registry=DOMAIN_METRICS_REGISTRY,
)
LLM_REQUESTS_TOTAL = Counter(
    "portfolio_llm_requests_total",
    "LLM provider requests by operation and outcome.",
    ("operation", "outcome"),
    registry=DOMAIN_METRICS_REGISTRY,
)
LLM_REQUEST_DURATION_SECONDS = Histogram(
    "portfolio_llm_request_duration_seconds",
    "LLM provider request latency in seconds by operation and outcome.",
    ("operation", "outcome"),
    buckets=LATENCY_BUCKETS,
    registry=DOMAIN_METRICS_REGISTRY,
)
CONTACT_SUBMISSIONS_TOTAL = Counter(
    "portfolio_contact_submissions_total",
    "Contact form submissions by outcome.",
    ("outcome",),
    registry=DOMAIN_METRICS_REGISTRY,
)
ESCALATION_EVENTS_TOTAL = Counter(
    "portfolio_escalation_events_total",
    "Human handoff escalation events by action and outcome.",
    ("action", "outcome"),
    registry=DOMAIN_METRICS_REGISTRY,
)
RATE_LIMIT_CHECKS_TOTAL = Counter(
    "portfolio_rate_limit_checks_total",
    "Rate limit checks by scope and outcome.",
    ("scope", "outcome"),
    registry=DOMAIN_METRICS_REGISTRY,
)
PAGE_VIEWS_TOTAL = Counter(
    "portfolio_page_views_total",
    "Privacy-safe aggregate page views by whitelisted page path.",
    ("page",),
    registry=DOMAIN_METRICS_REGISTRY,
)
RESUME_DOWNLOADS_TOTAL = Counter(
    "portfolio_resume_downloads_total",
    "Privacy-safe aggregate resume download clicks by whitelisted source.",
    ("source",),
    registry=DOMAIN_METRICS_REGISTRY,
)


def start_timer() -> float:
    return perf_counter()


def elapsed_seconds(start_time: float) -> float:
    return max(0.0, perf_counter() - start_time)


def record_chat_request(
    *,
    mode: str,
    outcome: str,
    policy_intent: str = "none",
) -> None:
    CHAT_REQUESTS_TOTAL.labels(
        mode=_safe_label(mode),
        outcome=_safe_label(outcome),
        policy_intent=_safe_label(policy_intent),
    ).inc()


def record_chat_response(
    *,
    mode: str,
    confidence: str,
    not_enough_data: bool,
    handoff_suggested: bool,
) -> None:
    CHAT_RESPONSES_TOTAL.labels(
        mode=_safe_label(mode),
        confidence=_safe_label(confidence),
        not_enough_data=_bool_label(not_enough_data),
        handoff_suggested=_bool_label(handoff_suggested),
    ).inc()


def record_chat_policy_decision(intent: str) -> None:
    CHAT_POLICY_DECISIONS_TOTAL.labels(intent=_safe_label(intent)).inc()


def record_rag_retrieval(
    *,
    outcome: str,
    chunks_count: int,
    duration_seconds: float,
) -> None:
    resolved_outcome = _safe_label(outcome)
    RAG_RETRIEVALS_TOTAL.labels(outcome=resolved_outcome).inc()
    RAG_RETRIEVAL_DURATION_SECONDS.labels(outcome=resolved_outcome).observe(duration_seconds)
    RAG_RETRIEVED_CHUNKS.observe(max(0, chunks_count))


def record_llm_request(
    *,
    operation: str,
    outcome: str,
    duration_seconds: float,
) -> None:
    resolved_operation = _safe_label(operation)
    resolved_outcome = _safe_label(outcome)
    LLM_REQUESTS_TOTAL.labels(
        operation=resolved_operation,
        outcome=resolved_outcome,
    ).inc()
    LLM_REQUEST_DURATION_SECONDS.labels(
        operation=resolved_operation,
        outcome=resolved_outcome,
    ).observe(duration_seconds)


def record_contact_submission(outcome: str) -> None:
    CONTACT_SUBMISSIONS_TOTAL.labels(outcome=_safe_label(outcome)).inc()


def record_escalation_event(*, action: str, outcome: str) -> None:
    ESCALATION_EVENTS_TOTAL.labels(
        action=_safe_label(action),
        outcome=_safe_label(outcome),
    ).inc()


def record_rate_limit_check(*, scope: str, outcome: str) -> None:
    RATE_LIMIT_CHECKS_TOTAL.labels(
        scope=_safe_label(scope),
        outcome=_safe_label(outcome),
    ).inc()


def record_page_view(page: str) -> None:
    if page not in SAFE_PAGE_LABELS:
        return
    PAGE_VIEWS_TOTAL.labels(page=page).inc()


def record_resume_download(source: str) -> None:
    if source not in SAFE_RESUME_DOWNLOAD_SOURCES:
        return
    RESUME_DOWNLOADS_TOTAL.labels(source=source).inc()


def domain_metrics_payload() -> bytes:
    from prometheus_client import generate_latest

    return generate_latest(DOMAIN_METRICS_REGISTRY)


def _safe_label(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized_value = value.strip().lower().replace("-", "_")
    if not normalized_value:
        return "unknown"
    return normalized_value[:80]


def _bool_label(value: bool) -> str:
    return "true" if value else "false"
