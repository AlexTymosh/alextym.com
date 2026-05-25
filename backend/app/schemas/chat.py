from typing import Literal

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["low", "medium", "high"]


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000,
        examples=["Tell me about Alex's recent projects"],
    )
    session_id: str | None = Field(default=None, max_length=100, examples=["optional-session-id"])

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


class ChatSource(BaseModel):
    title: str = Field(examples=["projects.md"])
    section: str | None = Field(default=None, examples=["fastapi-saas-template"])
    confidence: Confidence = Field(examples=["high"])


class ChatResponse(BaseModel):
    answer: str = Field(
        examples=[
            "I do not have enough reliable information in Alex's public knowledge base to answer "
            "that accurately."
        ]
    )
    sources: list[ChatSource] = Field(default_factory=list)
    confidence: Confidence = Field(examples=["low"])
    not_enough_data: bool = Field(examples=[True])
