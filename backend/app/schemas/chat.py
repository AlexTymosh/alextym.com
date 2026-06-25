from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.confidence import Confidence

ChatHistoryRole = Literal["user", "assistant"]
HandoffReason = Literal[
    "insufficient_data",
    "private_data",
    "language_unsupported",
    "user_requested_human",
    "availability_or_contact",
    "service_enquiry",
    "public_boundary",
]

MAX_CHAT_HISTORY_ITEMS = 10
MAX_CHAT_HISTORY_TOTAL_CHARS = 6000


class ChatHistoryMessage(BaseModel):
    role: ChatHistoryRole = Field(examples=["user"])
    content: str = Field(min_length=1, max_length=2000, examples=["Hi"])

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value:
            raise ValueError("History content must not be blank.")
        return value


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000,
        examples=["Tell me about Alex's recent projects"],
    )
    session_id: str | None = Field(
        default=None,
        max_length=100,
        examples=["optional-session-id"],
    )
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_CHAT_HISTORY_ITEMS,
        description=("Optional short prior conversation context. It is not a source of facts."),
    )

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value:
            raise ValueError("Message must not be blank.")
        return value

    @field_validator("session_id", mode="before")
    @classmethod
    def normalize_session_id(cls, value: object) -> object:
        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value or None
        return value

    @model_validator(mode="after")
    def reject_oversized_history(self) -> "ChatRequest":
        total_chars = sum(len(item.content) for item in self.history)
        if total_chars > MAX_CHAT_HISTORY_TOTAL_CHARS:
            raise ValueError("Chat history is too large.")
        return self


class ChatSource(BaseModel):
    title: str = Field(examples=["resume.md"])
    section: str | None = Field(default=None, examples=["Summary"])
    confidence: Confidence = Field(examples=["medium"])


class ChatResponse(BaseModel):
    answer: str = Field(
        examples=[
            "Sorry, I'm not sure I understood. Could you clarify, "
            "or should I connect you with Alex?"
        ]
    )
    sources: list[ChatSource] = Field(default_factory=list)
    confidence: Confidence = Field(examples=["low"])
    not_enough_data: bool = Field(examples=[True])
    handoff_suggested: bool = Field(
        default=False,
        description=(
            "Whether the frontend should offer an explicit human handoff prompt. "
            "This is a UI signal only; it must not trigger side effects without "
            "user consent."
        ),
        examples=[True],
    )
    handoff_reason: HandoffReason | None = Field(
        default=None,
        description="Reason for suggesting human handoff, when applicable.",
        examples=["insufficient_data"],
    )
    language_unsupported: bool = Field(
        default=False,
        description="Whether the request language is outside the public chat scope.",
        examples=[False],
    )
    user_requested_human: bool = Field(
        default=False,
        description="Whether the user explicitly asked for a human handoff.",
        examples=[False],
    )
