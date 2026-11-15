"""Project HTTP safety and host-provided request context."""

import logging
from collections.abc import Callable
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from workforce_intelligence.database import Database, DatabaseBusy, DatabaseUnavailable
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    RecordNotFound,
    ResetThrottled,
    ensure_dataset,
)
from workforce_intelligence.seed import INTERVIEW_SEED

logger = logging.getLogger(__name__)


def _error(status_code: int, detail: str, headers: dict | None = None) -> Response:
    return JSONResponse({"detail": detail}, status_code, headers=headers)


class WorkforceRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            try:
                response = await handler(request)
            except StarletteHTTPException as exc:
                response = _error(exc.status_code, exc.detail, exc.headers)
            except RequestValidationError:
                response = _error(
                    422, "Invalid Workforce request. Check the required fields and formats."
                )
            except InvalidOperation as exc:
                response = _error(422, str(exc))
            except RecordNotFound as exc:
                response = _error(404, str(exc))
            except Conflict as exc:
                response = _error(409, str(exc))
            except DatabaseBusy:
                response = _error(
                    409, "The dataset is busy. Refresh and retry.", {"Retry-After": "1"}
                )
            except ResetThrottled as exc:
                response = _error(
                    429,
                    "Wait before requesting another reset.",
                    {"Retry-After": str(exc.retry_after)},
                )
            except DatabaseUnavailable:
                logger.warning("Workforce storage unavailable")
                response = _error(503, "Workforce dataset unavailable. Retry shortly.")
            response.headers["Cache-Control"] = "no-store"
            return response

        return handle


def get_database() -> Database:
    return Database()


def seeded_database(database: Annotated[Database, Depends(get_database)]) -> Database:
    ensure_dataset(database, INTERVIEW_SEED)
    return database


def audit_actor(request: Request) -> AuditActor:
    # Only the host's successful membership dependency sets this state.
    uid = getattr(request.state, "workforce_uid", None)
    if not uid:
        raise HTTPException(401, "Authentication required")
    correlation_id = getattr(request.state, "request_id", None) or f"req_{uuid4().hex}"
    return AuditActor(uid, correlation_id)


Db = Annotated[Database, Depends(seeded_database)]
Member = Annotated[AuditActor, Depends(audit_actor)]
