import os

import pytest

from app.services.rate_limit import get_rate_limiter


os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    get_rate_limiter().reset()
    yield
    get_rate_limiter().reset()
