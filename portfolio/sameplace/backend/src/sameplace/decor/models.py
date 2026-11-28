"""Strict commands; only registered asset IDs and bounded integer coordinates."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from ..rooms.models import Command, Model, Name
from .catalog import ASSETS, BACKGROUNDS, LIGHTS, SKINS, SURFACES

Location = Literal["lounge", "table"]
Scope = Literal["room", "lounge", "table"]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,48}$")]


class DecorObject(Model):
    id: Identifier
    asset_id: Identifier
    x: int = Field(ge=8, le=92)
    y: int = Field(ge=12, le=88)
    scale: int = Field(ge=50, le=150)
    rotation: int = Field(ge=-180, le=180)
    z: int = Field(ge=0, le=9)


class Scene(Model):
    schema_version: Literal[1] = 1
    background: Identifier
    lighting: Identifier
    surface: Identifier
    skin: Identifier
    objects: list[DecorObject] = Field(max_length=16)

    @model_validator(mode="after")
    def validate_registry(self):
        if (
            self.background not in BACKGROUNDS
            or self.lighting not in LIGHTS
            or self.skin not in SKINS
            or self.surface not in SURFACES[self.background]
        ):
            raise ValueError("Unknown or incompatible scene asset")
        if len({o.id for o in self.objects}) != len(self.objects):
            raise ValueError("Duplicate object identifier")
        for o in self.objects:
            if ASSETS.get(o.asset_id, {}).get("kind") != "decor":
                raise ValueError("Unknown decor asset")
        return self


class PublishScene(Command):
    location: Location
    revision: int = Field(ge=0)
    room_version: int = Field(ge=1)
    scene: Scene


class SaveTemplate(Command):
    name: Name
    scene: Scene
    template_id: Identifier | None = None
    revision: int = Field(default=0, ge=0)


class DeleteTemplate(Command):
    template_id: Identifier
    revision: int = Field(ge=1)


class MusicCommand(Command):
    scope: Scope
    revision: int = Field(ge=0)
    action: Literal["select", "play", "pause", "stop", "seek", "inherit"]
    source_id: Identifier | None = None
    position_ms: int | None = Field(default=None, ge=0, le=3600000)

    @model_validator(mode="after")
    def validate_action(self):
        if (self.action == "select") != (self.source_id is not None):
            raise ValueError("Source required only for selection")
        if (self.action == "seek") != (self.position_ms is not None):
            raise ValueError("Position required only for seek")
        if self.action == "inherit" and self.scope == "room":
            raise ValueError("Room cannot inherit")
        return self
