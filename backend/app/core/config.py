import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    frontend_origin: str
    openai_model: str
    openai_embedding_model: str
    qdrant_collection: str
    rate_limiting_enabled: bool
    chat_daily_limit_per_ip: int


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


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "alextym API"),
        environment=os.getenv("ENVIRONMENT", "local"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", ""),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "alex_public_knowledge"),
        rate_limiting_enabled=_get_bool("RATE_LIMITING_ENABLED", True),
        chat_daily_limit_per_ip=_get_int("CHAT_DAILY_LIMIT_PER_IP", 50),
    )
