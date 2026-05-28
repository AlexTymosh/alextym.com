from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str = Field(examples=[123456789])
    type: str | None = Field(default=None, examples=["private"])


class TelegramReplyMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int = Field(examples=[100])
    text: str | None = None
    chat: TelegramChat | None = None


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int = Field(examples=[101])
    chat: TelegramChat
    text: str | None = None
    reply_to_message: TelegramReplyMessage | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int = Field(examples=[123456])
    message: TelegramMessage | None = None


class TelegramWebhookResponse(BaseModel):
    status: Literal["ok", "ignored"] = Field(examples=["ok"])
    handoff_id: str | None = Field(default=None, examples=["hnd_2d9f2c4e"])
