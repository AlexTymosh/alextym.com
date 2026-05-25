from pydantic import BaseModel, Field


class LiveResponse(BaseModel):
    status: str = Field(examples=["alive"])


class ReadyResponse(BaseModel):
    status: str = Field(examples=["ready"])
    app: str = Field(examples=["ready"])
    environment: str = Field(examples=["local"])
    vector_db: str = Field(examples=["not_configured"])
    llm_config: str = Field(examples=["not_configured"])
    contact_email: str = Field(examples=["not_configured"])


class WarmupResponse(BaseModel):
    status: str = Field(examples=["warmed"])
    app: str = Field(examples=["ready"])
    environment: str = Field(examples=["local"])
