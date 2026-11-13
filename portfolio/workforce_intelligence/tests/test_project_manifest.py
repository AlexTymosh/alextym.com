"""Verify project identity and isolated routes before enabling its UI."""

import json
from pathlib import Path


def test_project_manifest_is_registered_private_and_isolated() -> None:
    root = Path(__file__).resolve().parents[3]
    registry = json.loads((root / "portfolio/catalog/registry.json").read_text(encoding="utf8"))
    manifest = json.loads(
        (root / "portfolio/workforce_intelligence/project.json").read_text(encoding="utf8")
    )
    assert "workforce_intelligence" in registry["projectIds"]
    assert "fleet_hub" in registry["projectIds"]
    assert manifest["id"] == "workforce_intelligence"
    assert manifest["demo"] == {
        "path": "/portfolio/workforce-intelligence",
        "apiPrefix": "/api/workforce",
    }
    assert manifest["catalog"] == {"visible": False, "featured": False}
    assert (root / "portfolio/fleet_hub/project.json").exists()
