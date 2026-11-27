"""Actual HTTP composition and dependency-direction checks in a full repository."""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.security import sameplace_access


@pytest.fixture
def host_client():
    from app.main import app

    # Do not start the host lifespan or external services in this routing test.
    return TestClient(app)


def test_host_disabled_sameplace_never_checks_identity(monkeypatch, host_client):
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "false")
    verify = Mock(side_effect=AssertionError("Unexpected identity lookup"))
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    assert host_client.get("/api/sameplace/status").status_code == 404
    verify.assert_not_called()


@pytest.mark.parametrize("code", [401, 403, 503])
def test_host_sameplace_rejects_unverified_access(monkeypatch, host_client, code):
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    verify = Mock(side_effect=HTTPException(code, "Synthetic access rejection"))
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    response = host_client.get("/api/sameplace/status")
    assert response.status_code == code
    assert response.json() == {"detail": "Synthetic access rejection"}
    verify.assert_called_once()
    assert verify.call_args.args[1] == "sameplace"


def test_host_mounts_the_guarded_router(monkeypatch, host_client):
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    verify = Mock(return_value={"uid": "synthetic-member"})
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    response = host_client.get("/api/sameplace/status")
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "sameplace",
        "stage": "foundation",
        "contract_version": 1,
    }
    verify.assert_called_once()
    assert verify.call_args.args[1] == "sameplace"
    assert host_client.post("/api/sameplace/status").status_code == 405
    verify.assert_called_once()


def test_host_preserves_legacy_preferans_route(host_client):
    # DELETE matches neither GET nor POST on this known legacy path. A 405
    # proves the path is mounted without executing a guard or database handler.
    assert host_client.delete("/api/preferans/rooms").status_code == 405


def test_contracts_and_host_import_only_their_owned_layers():
    repo = Path(__file__).resolve().parents[3]
    contracts = repo / "portfolio/sameplace/backend/src/sameplace/contracts"
    for source in contracts.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [name.name for name in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                assert module.split(".")[0] in {"typing", "pydantic"}, (source, module)
    host = repo / "backend/app"
    for source in host.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = [name.name for name in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if module.split(".")[0] == "sameplace":
                    assert source == host / "main.py" and module == "sameplace.router"
