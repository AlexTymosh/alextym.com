"""Positive and negative fixture tests for the Python import architecture guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_import_boundaries import scan_import_boundaries


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for folder in (
        "backend/app/domain",
        "backend/app/repositories",
        "backend/app/services",
        "backend/app/rag",
        "backend/app/llm",
        "portfolio/fleet_hub/backend/src/fleet_hub/api",
        "portfolio/fleet_hub/backend/src/fleet_hub/services",
    ):
        target = tmp_path / folder
        target.mkdir(parents=True)
        (target / "__init__.py").write_text("", encoding="utf-8")
    return tmp_path


def put(repo: Path, path: str, source: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def errors(repo: Path) -> list[str]:
    return [item.format() for item in scan_import_boundaries(repo)]


def test_valid_domain_repository_service_and_shared_fleet_dependencies(repository: Path) -> None:
    put(repository, "backend/app/domain/state.py", "from dataclasses import dataclass\n")
    put(
        repository,
        "backend/app/repositories/store.py",
        "from app.domain.state import Record\nfrom app.repositories import other\n",
    )
    put(
        repository,
        "portfolio/fleet_hub/backend/src/fleet_hub/services/use_case.py",
        "from fleet_hub.persistence.sqlite import open_sqlite\n",
    )
    put(
        repository,
        "portfolio/fleet_hub/backend/src/fleet_hub/api/vor_reporting.py",
        "from fleet_hub.api.dependencies import required\n"
        "from fleet_hub.services import vor_store\n",
    )
    assert errors(repository) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from app.services.escalation import EscalationService", "app.services.escalation"),
        ("import app.services.escalation as svc", "app.services.escalation"),
        ("from app import services", "app.services"),
        ("from app.api import escalation", "app.api"),
        ("from ..services import escalation", "app.services"),
        ("importlib.import_module('app.services.escalation')", "app.services.escalation"),
        ("__import__('app.services.escalation')", "app.services.escalation"),
    ],
)
def test_repository_to_service_and_api_imports_are_rejected(
    repository: Path, source: str, expected: str
) -> None:
    put(repository, "backend/app/repositories/broken.py", source + "\n")
    result = errors(repository)
    assert any(expected in line for line in result), result
    assert all("backend/app/repositories/broken.py:1:" in line for line in result)


@pytest.mark.parametrize(
    "source",
    [
        "from app.core import config",
        "from app.repositories import store",
        "import app.api",
        "import app.services",
    ],
)
def test_domain_must_remain_independent(repository: Path, source: str) -> None:
    put(repository, "backend/app/domain/broken.py", source + "\n")
    assert len(errors(repository)) >= 1


def test_domain_may_import_another_domain_module(repository: Path) -> None:
    put(
        repository,
        "backend/app/domain/nested.py",
        "from app.domain import state\nfrom app import domain\n",
    )
    assert errors(repository) == []


@pytest.mark.parametrize(
    "source",
    [
        "from fleet_hub.api.vor import create_message",
        "from ..api import vor",
        "import fleet_hub.api.vor",
        "from app.api import escalation",
        "from importlib import import_module\nimport_module('fleet_hub.api.vor')",
    ],
)
def test_fleet_service_cannot_import_api(repository: Path, source: str) -> None:
    put(repository, "portfolio/fleet_hub/backend/src/fleet_hub/services/bad.py", source + "\n")
    assert len(errors(repository)) >= 1


def test_fleet_router_can_import_shared_service_without_sibling_router(repository: Path) -> None:
    put(
        repository,
        "portfolio/fleet_hub/backend/src/fleet_hub/api/vor.py",
        "from fleet_hub.api.dependencies import same_origin\n"
        "from fleet_hub.services.vor_checklist_advance import advance_with_checks\n",
    )
    assert errors(repository) == []


def test_former_legacy_router_edge_is_now_forbidden(repository: Path) -> None:
    put(
        repository,
        "portfolio/fleet_hub/backend/src/fleet_hub/api/vor.py",
        "from fleet_hub.api.vor_checklist import advance_with_checks\n",
    )
    result = errors(repository)
    assert result
    assert any("fleet_hub.api.vor_checklist" in line for line in result)


def test_new_sibling_router_imports_blocked_including_relative(repository: Path) -> None:
    put(
        repository,
        "portfolio/fleet_hub/backend/src/fleet_hub/api/vor_reporting.py",
        "from . import vor_checklist\n",
    )
    result = errors(repository)
    assert any("fleet_hub.api.vor_checklist" in line for line in result)
    assert any(":1:" in line for line in result)


def test_unknown_sibling_edge_from_vor_not_exempt(repository: Path) -> None:
    put(
        repository,
        "portfolio/fleet_hub/backend/src/fleet_hub/api/vor.py",
        "from fleet_hub.api.vor_reporting import something\n",
    )
    assert errors(repository)


def test_comments_and_string_literals_are_not_imports(repository: Path) -> None:
    put(
        repository,
        "backend/app/repositories/store.py",
        "# import app.services.bad\nphrase = 'from app.services import other'\n",
    )
    assert errors(repository) == []


def test_missing_root_does_not_silently_pass(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scan_import_boundaries(tmp_path)


def test_invalid_python_is_not_silently_skipped(repository: Path) -> None:
    put(repository, "backend/app/repositories/bad.py", "from \n")
    with pytest.raises(SyntaxError):
        scan_import_boundaries(repository)


def register_additional_project(repo: Path) -> None:
    import json

    put(repo, "portfolio/fleet_hub/backend/src/fleet_hub/__init__.py", "")
    put(repo, "portfolio/recruitment_analytics/backend/src/recruit_analytics/__init__.py", "")
    put(
        repo,
        "portfolio/recruitment_analytics/backend/src/recruit_analytics/services/__init__.py",
        "",
    )
    put(
        repo,
        "portfolio/catalog/registry.json",
        json.dumps({"schemaVersion": 1, "projectIds": ["fleet_hub", "recruitment_analytics"]}),
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from app.services import mail", "website internals"),
        ("import app.api", "website internals"),
        ("from recruit_analytics.services import report", "another project"),
        ("import recruit_analytics.services", "another project"),
    ],
)
def test_registered_project_imports_cannot_cross_boundaries(
    repository: Path, source: str, expected: str
) -> None:
    register_additional_project(repository)
    put(repository, "portfolio/fleet_hub/backend/src/fleet_hub/services/illegal.py", source + "\n")
    assert any(expected in message for message in errors(repository))


def test_new_project_internal_imports_are_allowed(repository: Path) -> None:
    register_additional_project(repository)
    put(
        repository,
        "portfolio/recruitment_analytics/backend/src/recruit_analytics/services/report.py",
        "from pathlib import Path\nfrom recruit_analytics.services import helper\n",
    )
    assert errors(repository) == []


def test_missing_registered_backend_does_not_pass(repository: Path) -> None:
    import shutil

    register_additional_project(repository)
    shutil.rmtree(repository / "portfolio/recruitment_analytics/backend")
    with pytest.raises(FileNotFoundError, match="Registered project backend missing"):
        scan_import_boundaries(repository)
