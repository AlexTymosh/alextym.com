"""Site-only architecture import rules; Fleet conventions remain unchanged."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_import_boundaries import scan_import_boundaries


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for package in (
        "backend/app/domain",
        "backend/app/repositories",
        "backend/app/services",
        "backend/app/rag",
        "backend/app/llm",
        "portfolio/fleet_hub/backend/src/fleet_hub/api",
        "portfolio/fleet_hub/backend/src/fleet_hub/services",
    ):
        folder = tmp_path / package
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


def scan(repo: Path, path: str, source: str) -> list[str]:
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(source + "\n", encoding="utf-8")
    return [violation.format() for violation in scan_import_boundaries(repo)]


@pytest.mark.parametrize(
    ("path", "source", "target"),
    [
        (
            "backend/app/services/bad.py",
            "from app.api import chat",
            "app.api",
        ),
        (
            "backend/app/services/bad.py",
            "import app.api.chat as http_chat",
            "app.api.chat",
        ),
        (
            "backend/app/services/bad.py",
            "from ..api import chat",
            "app.api",
        ),
        (
            "backend/app/services/bad.py",
            "from app import api",
            "app.api",
        ),
        (
            "backend/app/rag/bad.py",
            "from app.api.chat import router",
            "app.api.chat",
        ),
        (
            "backend/app/rag/bad.py",
            "from app.services.chat import ChatService",
            "app.services.chat",
        ),
        (
            "backend/app/llm/bad.py",
            "import app.api.escalation as escalation_api",
            "app.api.escalation",
        ),
        (
            "backend/app/llm/bad.py",
            "__import__('app.api.chat')",
            "app.api.chat",
        ),
        (
            "backend/app/services/bad.py",
            "importlib.import_module('app.api.chat')",
            "app.api.chat",
        ),
        (
            "backend/app/rag/bad.py",
            "from importlib import import_module\nimport_module('app.services.chat')",
            "app.services.chat",
        ),
    ],
)
def test_forbidden_site_imports(
    repository: Path,
    path: str,
    source: str,
    target: str,
) -> None:
    result = scan(repository, path, source)
    assert any(target in line for line in result), result
    assert all(path in line for line in result)


def test_existing_valid_composition_edges_remain_allowed(repository: Path) -> None:
    assert (
        scan(
            repository,
            "backend/app/services/chat.py",
            "from app.rag.retriever import Retriever\n"
            "from app.llm.client import LLMClient\n"
            "from app.repositories.escalation_session_store import EscalationSessionStore",
        )
        == []
    )
    assert (
        scan(
            repository,
            "backend/app/rag/retriever.py",
            "from app.llm.client import EmbeddingClient\nfrom app.core.config import Settings",
        )
        == []
    )
    # Known existing dependency in the main site: do not ban it by accident.
    assert (
        scan(
            repository,
            "backend/app/llm/factory.py",
            "from app.services.question_contextualizer import QuestionContextualizer",
        )
        == []
    )


@pytest.mark.parametrize(
    "source",
    [
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.api import chat",
        "import typing\nif typing.TYPE_CHECKING:\n    import app.api.chat as chat",
        "from typing import TYPE_CHECKING as ONLY_TYPES\n"
        "if ONLY_TYPES:\n    from app.api.chat import chat",
    ],
)
def test_type_checking_imports_do_not_create_runtime_site_edges(
    repository: Path,
    source: str,
) -> None:
    assert scan(repository, "backend/app/services/annotations.py", source) == []


def test_type_checking_else_branch_is_a_runtime_dependency(repository: Path) -> None:
    result = scan(
        repository,
        "backend/app/services/annotations.py",
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n    from app.core.config import Settings\n"
        "else:\n    from app.api.chat import chat",
    )
    assert any("app.api.chat" in item for item in result)


def test_comments_strings_and_legitimate_relative_imports_are_ignored(
    repository: Path,
) -> None:
    assert (
        scan(
            repository,
            "backend/app/rag/models.py",
            "# from app.api.chat import chat\n"
            "text = 'import app.services.chat'\n"
            "from . import retriever",
        )
        == []
    )


def test_guard_reports_exact_file_and_line(repository: Path) -> None:
    result = scan(
        repository,
        "backend/app/services/bad.py",
        "from app.core.config import Settings\nfrom app.api import chat",
    )
    assert any("backend/app/services/bad.py:2:" in item for item in result)


def test_unrelated_runtime_type_checking_flag_is_not_exempt(repository: Path) -> None:
    result = scan(
        repository,
        "backend/app/services/bad.py",
        "TYPE_CHECKING = True\nif TYPE_CHECKING:\n    from app.api import chat",
    )
    assert any("app.api" in item for item in result)


@pytest.mark.parametrize(
    ("path", "source"),
    [
        (
            "backend/app/domain/bad.py",
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    from app.services import chat",
        ),
        (
            "backend/app/repositories/bad.py",
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.api import chat",
        ),
        (
            "portfolio/fleet_hub/backend/src/fleet_hub/services/bad.py",
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n    from fleet_hub.api import vor",
        ),
    ],
)
def test_existing_architecture_rules_are_not_weakened(
    repository: Path,
    path: str,
    source: str,
) -> None:
    assert scan(repository, path, source)
