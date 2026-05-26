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
    rate_limiting_enabled: bool
    chat_daily_limit_per_ip: int


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
        rate_limiting_enabled=_get_bool("RATE_LIMITING_ENABLED", True),
        chat_daily_limit_per_ip=_get_int("CHAT_DAILY_LIMIT_PER_IP", 50),
    )
