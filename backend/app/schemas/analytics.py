from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnalyticsEventType = Literal["page_view", "resume_download"]
AnalyticsPage = Literal["/", "/resume", "/chat", "/contact"]
AnalyticsSource = Literal["resume_page"]


class AnalyticsEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: AnalyticsEventType = Field(examples=["page_view"])
    page: AnalyticsPage | None = Field(default=None, examples=["/resume"])
    source: AnalyticsSource | None = Field(default=None, examples=["resume_page"])

    @model_validator(mode="after")
    def validate_event_payload(self) -> "AnalyticsEventRequest":
        if self.event == "page_view" and self.page is None:
            raise ValueError("Page view analytics events require a whitelisted page.")
        if self.event == "resume_download" and self.source is None:
            raise ValueError("Resume download analytics events require a source.")
        return self


class AnalyticsEventResponse(BaseModel):
    status: str = Field(default="accepted", examples=["accepted"])
