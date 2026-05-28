import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    frontend_origin: str
    openai_api_key: str
    openai_model: str
    openai_embedding_model: str
    openai_embedding_dimensions: int
    openai_max_output_tokens: int
    openai_reasoning_effort: str
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection: str
    rag_top_k: int
    rag_score_threshold: float
    resend_api_key: str
    contact_target_email: str
    contact_from_email: str
    rate_limiting_enabled: bool
    chat_daily_limit_per_ip: int
    contact_daily_limit_per_ip: int
    telegram_bot_token: str = ""
    telegram_owner_chat_id: str = ""
    escalation_daily_limit_per_ip: int = 3
    escalation_transcript_max_messages: int = 20
    escalation_transcript_max_chars: int = 8000
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    escalation_session_ttl_seconds: int = 7200


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, raw_value = line.split("=", 1)
        name = name.strip()
        if not name or name in os.environ:
            continue

        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ[name] = value


def _load_local_env_file() -> None:
    if os.getenv("ENVIRONMENT") == "test":
        return

    for env_path in _local_env_candidates():
        if env_path.exists():
            _load_env_file(env_path)
            return


def _local_env_candidates() -> tuple[Path, ...]:
    cwd = Path.cwd()
    return (
        cwd / ".env",
        cwd / "backend" / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    )


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


@lru_cache
def get_settings() -> Settings:
    _load_local_env_file()

    return Settings(
        app_name=os.getenv("APP_NAME", "alextym API"),
        environment=os.getenv("ENVIRONMENT", "local"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_embedding_dimensions=_get_int("OPENAI_EMBEDDING_DIMENSIONS", 1536),
        openai_max_output_tokens=_get_int("OPENAI_MAX_OUTPUT_TOKENS", 600),
        openai_reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "low"),
        qdrant_url=os.getenv("QDRANT_URL", ""),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "alex_public_knowledge"),
        rag_top_k=_get_int("RAG_TOP_K", 6),
        rag_score_threshold=_get_float("RAG_SCORE_THRESHOLD", 0.4),
        resend_api_key=os.getenv("RESEND_API_KEY", ""),
        contact_target_email=os.getenv("CONTACT_TARGET_EMAIL", ""),
        contact_from_email=os.getenv("CONTACT_FROM_EMAIL", ""),
        rate_limiting_enabled=_get_bool("RATE_LIMITING_ENABLED", True),
        chat_daily_limit_per_ip=_get_int("CHAT_DAILY_LIMIT_PER_IP", 50),
        contact_daily_limit_per_ip=_get_int("CONTACT_DAILY_LIMIT_PER_IP", 5),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_owner_chat_id=os.getenv("TELEGRAM_OWNER_CHAT_ID", ""),
        escalation_daily_limit_per_ip=_get_int("ESCALATION_DAILY_LIMIT_PER_IP", 3),
        escalation_transcript_max_messages=_get_int("ESCALATION_TRANSCRIPT_MAX_MESSAGES", 20),
        escalation_transcript_max_chars=_get_int("ESCALATION_TRANSCRIPT_MAX_CHARS", 8000),
        upstash_redis_rest_url=os.getenv("UPSTASH_REDIS_REST_URL", ""),
        upstash_redis_rest_token=os.getenv("UPSTASH_REDIS_REST_TOKEN", ""),
        escalation_session_ttl_seconds=_get_int("ESCALATION_SESSION_TTL_SECONDS", 7200),
    )
