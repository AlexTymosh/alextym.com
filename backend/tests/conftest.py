import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.services.rate_limit import get_rate_limiter


os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    get_rate_limiter().reset()
    yield
    get_rate_limiter().reset()


@pytest.fixture
def empty_chat_client() -> Iterator[TestClient]:
    from app.api.chat import get_chat_service
    from app.main import app
    from app.rag.retriever import EmptyRetriever
    from app.services.chat import ChatService

    app.dependency_overrides[get_chat_service] = lambda: ChatService(retriever=EmptyRetriever())
    yield TestClient(app)
    app.dependency_overrides.clear()
