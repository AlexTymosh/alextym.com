"""Validate the metadata seam without claiming any real game implementation."""

from copy import deepcopy

import pytest
from pydantic import ValidationError
from sameplace.contracts.activity import ActivityManifest


def fixture(module_id="fixture_table", counts=None):
    counts = counts or [2, 4]
    return {
        "module_id": module_id,
        "module_version": "0.1.0",
        "contract_version": 1,
        "state_schema_version": 1,
        "rules_schema_version": 1,
        "display_name_key": f"activities.{module_id}.title",
        "kind": "turn_based",
        "players": {"min": min(counts), "max": max(counts), "allowed": counts},
        "roles": {"game_master": "none"},
        "capabilities": {
            "pause": True,
            "resume": True,
            "spectators": True,
            "bots": False,
            "replace_controller": False,
            "rankings": False,
            "hidden_information": True,
            "reconnect": True,
        },
        "spectator_modes": ["social_only", "public_summary"],
        "layout_profiles": ["fixture_layout"],
        "supported_locales": ["ru"],
        "supported_scene_surfaces": ["table", "mat"],
        "rules_schema_ref": f"{module_id}.rules.v1",
        "ui_entrypoint_key": module_id,
    }


def test_two_independent_metadata_examples():
    table = ActivityManifest.model_validate(fixture())
    social = fixture("fixture_social", [3, 5, 6])
    social["kind"] = "social"
    social["roles"]["game_master"] = "required"
    social["capabilities"]["hidden_information"] = False
    second = ActivityManifest.model_validate(social)
    assert table.module_id != second.module_id
    assert second.players.allowed == [3, 5, 6]
    assert second.roles.game_master == "required"
    assert ActivityManifest.model_validate_json(table.model_dump_json()) == table


@pytest.mark.parametrize(
    "change",
    [
        {"contract_version": 2},
        {"contract_version": "1"},
        {"contract_version": True},
        {"contract_version": 1.0},
        {"module_id": "../legacy"},
        {"module_version": "01.0.0"},
        {"state_schema_version": 0},
        {"display_name_key": "activities.other.title"},
        {"supported_locales": ["ru", "ru"]},
        {"supported_locales": ["../ru"]},
        {"supported_scene_surfaces": ["table", "table"]},
        {"players": {"min": 2, "max": 4, "allowed": [2, 3]}},
        {"players": {"min": 2, "max": 4, "allowed": [2, 2, 4]}},
        {"players": {"min": 1, "max": 11, "allowed": [1, 11]}},
        {"spectator_modes": []},
        {"ui_entrypoint_key": "https://example.invalid/plugin.js"},
        {"executable_url": "https://example.invalid/plugin.js"},
    ],
)
def test_invalid_metadata_rejected(change):
    invalid = deepcopy(fixture())
    invalid.update(change)
    with pytest.raises(ValidationError):
        ActivityManifest.model_validate(invalid)


def test_resume_requires_pause():
    data = fixture()
    data["capabilities"]["pause"] = False
    with pytest.raises(ValidationError, match="resume requires pause"):
        ActivityManifest.model_validate(data)


def test_future_language_metadata_does_not_enable_a_runtime_locale():
    data = fixture()
    data["supported_locales"] = ["ru", "en-GB"]
    assert ActivityManifest.model_validate(data).supported_locales == ["ru", "en-GB"]
