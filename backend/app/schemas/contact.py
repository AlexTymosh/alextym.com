import re

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["John Smith"])
    email: str = Field(min_length=3, max_length=254, examples=["john@example.com"])
    message: str = Field(
        min_length=1, max_length=4000, examples=["I would like to discuss a role."]
    )
    company_website: str | None = Field(default=None, max_length=200, examples=[""])

    @field_validator("name", "email", "message", "company_website", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("name", "message")
    @classmethod
    def reject_blank_required_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Field must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized_email = value.lower()
        if not EMAIL_PATTERN.match(normalized_email):
            raise ValueError("Email address is not valid.")
        return normalized_email

    @field_validator("company_website")
    @classmethod
    def normalize_honeypot(cls, value: str | None) -> str | None:
        return value or None

    @property
    def is_honeypot_filled(self) -> bool:
        return bool(self.company_website)


class ContactResponse(BaseModel):
    status: str = Field(default="ok", examples=["ok"])
