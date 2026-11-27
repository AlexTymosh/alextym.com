"""SP01 manifest contract, not a plugin loader or a playable module."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
Version = Annotated[
    str,
    StringConstraints(
        pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$", max_length=32
    ),
]
TranslationKey = Annotated[
    str,
    StringConstraints(pattern=r"^activities\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$", max_length=128),
]
Count = Annotated[int, Field(ge=1, le=10)]
SchemaVersion = Annotated[int, Field(ge=1)]
ContractVersion = Annotated[int, Field(ge=1, le=1)]
LocaleTag = Annotated[
    str, StringConstraints(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$", max_length=35)
]
Reference = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.]*$", max_length=128)]
SpectatorMode = Literal["social_only", "public_summary", "public_board"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Players(Contract):
    min: Count
    max: Count
    allowed: Annotated[list[Count], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.allowed != sorted(set(self.allowed)):
            raise ValueError("allowed counts must be sorted and unique")
        if self.min != self.allowed[0] or self.max != self.allowed[-1]:
            raise ValueError("allowed counts must match the declared range")
        return self


class Roles(Contract):
    game_master: Literal["none", "optional_non_privileged", "optional", "required"]


class Capabilities(Contract):
    pause: bool
    resume: bool
    spectators: bool
    bots: bool
    replace_controller: bool
    rankings: bool
    hidden_information: bool
    reconnect: bool


class ActivityManifest(Contract):
    module_id: Identifier
    module_version: Version
    contract_version: ContractVersion
    state_schema_version: SchemaVersion
    rules_schema_version: SchemaVersion
    display_name_key: TranslationKey
    kind: Literal["turn_based", "realtime", "adventure", "social"]
    players: Players
    roles: Roles
    capabilities: Capabilities
    spectator_modes: Annotated[list[SpectatorMode], Field(max_length=3)]
    layout_profiles: Annotated[list[Identifier], Field(min_length=1, max_length=32)]
    supported_locales: Annotated[list[LocaleTag], Field(min_length=1, max_length=32)]
    supported_scene_surfaces: Annotated[list[Identifier], Field(min_length=1, max_length=32)]
    rules_schema_ref: Reference
    ui_entrypoint_key: Identifier

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if not self.display_name_key.startswith(f"activities.{self.module_id}."):
            raise ValueError("display name must belong to the module namespace")
        if self.capabilities.resume and not self.capabilities.pause:
            raise ValueError("resume requires pause")
        if bool(self.spectator_modes) != self.capabilities.spectators:
            raise ValueError("spectator modes must match spectator capability")
        for values in (
            self.spectator_modes,
            self.layout_profiles,
            self.supported_locales,
            self.supported_scene_surfaces,
        ):
            if len(values) != len(set(values)):
                raise ValueError("manifest lists must not contain duplicates")
        return self
