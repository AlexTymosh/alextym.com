"""Versioned room commands and identity, without transport or storage dependencies."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

UID = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[^/\x00-\x1f]+$")]
Slug = Annotated[
    str, StringConstraints(min_length=3, max_length=48, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
]
Key = Annotated[str, StringConstraints(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Role = Literal["designer", "moderator", "dj", "organizer", "inviter"]
Interior = Literal["apartment", "garage", "beach", "kindergarten_boat", "card_club"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Actor(Model):
    uid: UID
    verified_email: str | None = None
    platform_owner: bool = False


class Command(Model):
    request_id: Key


class Versioned(Command):
    version: int = Field(ge=1)


class CreateRoom(Command):
    slug: Slug
    name: Name
    capacity: int = Field(ge=2, le=10)
    interior: Interior = "apartment"

    @field_validator("slug")
    @classmethod
    def reserved(cls, value: str) -> str:
        if value in {
            "api",
            "rooms",
            "settings",
            "friends",
            "catalog",
            "admin",
            "login",
            "history",
            "design",
        }:
            raise ValueError("Reserved slug")
        return value


class UpdateRoom(Versioned):
    name: Name
    capacity: int = Field(ge=2, le=10)
    interior: Interior


class DesignRoom(Versioned):
    interior: Interior


class MemberCommand(Versioned):
    uid: UID


class SetRoles(MemberCommand):
    roles: list[Role] = Field(max_length=5)

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, value: list[Role]) -> list[Role]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate role")
        return value


class Invite(Versioned):
    target_kind: Literal["uid", "email"]
    target: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    days: int = Field(default=7, ge=1, le=30)

    @field_validator("target")
    @classmethod
    def valid_target(cls, value, info):
        if info.data.get("target_kind") == "uid":
            if len(value) > 128 or "/" in value or any(ord(c) < 32 for c in value):
                raise ValueError("Invalid UID")
        elif (
            value.count("@") != 1
            or any(c.isspace() or ord(c) < 32 for c in value)
            or not all(value.split("@"))
        ):
            raise ValueError("Invalid email")
        return value


class Redeem(Command):
    token: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$")]


class RevokeInvite(Versioned):
    invite_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]


class TransferAccept(Versioned):
    transfer_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]


class Approval(Command):
    uid: UID
    approved: bool


class Limits(Command):
    storage_rooms: int = Field(ge=1, le=300)
    active_rooms: int = Field(ge=1, le=30)
    active_participants: int = Field(ge=2, le=100)
    capacity_ceiling: int = Field(ge=2, le=10)
