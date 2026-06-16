from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str = Field(examples=[123456789])
    is_bot: bool | None = None
    first_name: str | None = None
    username: str | None = None


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


class TelegramCallbackQuery(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(examples=["1234567890123456789"])
    from_user: TelegramUser | None = Field(default=None, alias="from")
    message: TelegramReplyMessage | None = None
    data: str | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int = Field(examples=[123456])
    message: TelegramMessage | None = None
    callback_query: TelegramCallbackQuery | None = None


class TelegramWebhookResponse(BaseModel):
    status: Literal["ok", "ignored"] = Field(examples=["ok"])
    handoff_id: str | None = Field(default=None, examples=["hnd_2d9f2c4e"])
