from app.core.config import Settings, get_settings
from app.rag.knowledge_base import get_public_retriever
from app.rag.qdrant_retriever import QdrantRetriever
from app.rag.retriever import Retriever


def get_configured_retriever(settings: Settings | None = None) -> Retriever:
    resolved_settings = settings or get_settings()
    if resolved_settings.openai_api_key and resolved_settings.qdrant_url:
        return QdrantRetriever.from_settings(resolved_settings)
    return get_public_retriever()
