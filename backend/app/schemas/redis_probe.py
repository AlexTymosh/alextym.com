from typing import Literal

from pydantic import BaseModel


class RedisProbeResponse(BaseModel):
    status: Literal["ok"] = "ok"
