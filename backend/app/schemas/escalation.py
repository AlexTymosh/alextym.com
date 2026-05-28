from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

EscalationRole = Literal["user", "assistant"]

MAX_ESCALATION_TRANSCRIPT_MESSAGES = 20
MAX_ESCALATION_TRANSCRIPT_TOTAL_CHARS = 8000


class EscalationTranscriptMessage(BaseModel):
    role: EscalationRole = Field(examples=["user"])
    content: str = Field(min_length=1, max_length=2000, examples=["Can I speak to Alex?"])

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
            raise ValueError("Transcript content must not be blank.")
        return value


class EscalationRequest(BaseModel):
    consent_accepted: bool = Field(examples=[True])
    reason: str = Field(
        min_length=1,
        max_length=100,
        examples=["user_requested_human"],
    )
    transcript: list[EscalationTranscriptMessage] = Field(
        min_length=1,
        max_length=MAX_ESCALATION_TRANSCRIPT_MESSAGES,
        description="Current chat transcript shared with Alex after explicit user consent.",
    )
    company_website: str | None = Field(default=None, max_length=200, examples=[""])

    @field_validator("reason", "company_website", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("reason")
    @classmethod
    def reject_blank_reason(cls, value: str) -> str:
        if not value:
            raise ValueError("Reason must not be blank.")
        return value

    @field_validator("company_website")
    @classmethod
    def normalize_honeypot(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def validate_escalation_request(self) -> "EscalationRequest":
        if not self.consent_accepted:
            raise ValueError("Escalation requires explicit user consent.")

        total_chars = sum(len(item.content) for item in self.transcript)
        if total_chars > MAX_ESCALATION_TRANSCRIPT_TOTAL_CHARS:
            raise ValueError("Escalation transcript is too large.")

        return self

    @property
    def is_honeypot_filled(self) -> bool:
        return bool(self.company_website)


class EscalationResponse(BaseModel):
    status: str = Field(default="ok", examples=["ok"])
