"""Strict social commands; stable machine identifiers are independent of locale."""

from typing import Annotated, Literal
from pydantic import Field, StringConstraints, field_validator
from ..rooms.models import Command, Model

PublicID = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
Location = Literal["lounge", "table"]


class Privacy(Model):
    show_online: bool = True
    show_room: bool = False
    show_activity: bool = False
    show_last_seen: bool = False
    allow_friend_invites: bool = True
    allow_nonfriend_invites: bool = False
    allow_email_pings: bool = False
    allow_sms_pings: bool = False


class Profile(Command):
    nickname: Nickname
    avatar: Literal["initials", "circle", "star", "leaf"] = "initials"
    privacy: Privacy

    @field_validator("nickname")
    @classmethod
    def safe_nickname(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Invalid nickname")
        return value


class Friend(Command):
    target: PublicID
    action: Literal["request", "accept", "decline", "cancel", "remove", "block", "unblock"]


class Favourite(Command):
    enabled: bool


class ChatSend(Command):
    text: Text

    @field_validator("text")
    @classmethod
    def plain_text(cls, value):
        if any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Invalid control character")
        return value


class ChatPage(Model):
    before: PublicID


class ChatHide(Command):
    message_id: PublicID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""


class Ping(Command):
    recipients: list[PublicID] = Field(min_length=1, max_length=10)
    channel: Literal["internal", "email", "sms"]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]

    @field_validator("recipients")
    @classmethod
    def unique(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Duplicate recipient")
        return value


class TicketRequest(Model):
    origin: Annotated[str, StringConstraints(min_length=8, max_length=250)]


class Proposal(Command):
    location: Location
    role: Literal["visit", "watch", "play"]
    recipients: list[PublicID] = Field(min_length=1, max_length=9)

    @field_validator("recipients")
    @classmethod
    def unique(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Duplicate recipient")
        return value


class ProposalAnswer(Command):
    proposal_id: PublicID
    accept: bool


class Move(Command):
    location: Location


class NoticeRead(Command):
    notice_id: PublicID


class ProposalCancel(Command):
    proposal_id: PublicID
