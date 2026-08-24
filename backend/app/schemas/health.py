from typing import Literal

from pydantic import BaseModel, Field

ReadyStatus = Literal["ready", "not_ready"]
VectorDbStatus = Literal["ready", "not_ready", "not_configured"]
ConfigurationStatus = Literal["configured", "not_configured"]


class LiveResponse(BaseModel):
    status: str = Field(examples=["alive"])


class ReadyResponse(BaseModel):
    status: ReadyStatus = Field(examples=["ready"])
    app: Literal["ready"] = Field(examples=["ready"])
    environment: str = Field(examples=["local"])
    vector_db: VectorDbStatus = Field(examples=["not_configured"])
    llm_config: ConfigurationStatus = Field(examples=["not_configured"])
    contact_email: ConfigurationStatus = Field(examples=["not_configured"])


class WarmupResponse(BaseModel):
    status: str = Field(examples=["warmed"])
    app: str = Field(examples=["ready"])
    environment: str = Field(examples=["local"])
