"""Bound file traffic after the shared Member dependency has succeeded."""

from fastapi import HTTPException, Request, Response
from starlette.requests import ClientDisconnect

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import AuditActor
from workforce_intelligence.workbook_import import WorkbookThrottled, limit_workbooks
from workforce_intelligence.workbook_model import MAX_UPLOAD_BYTES, XLSX_TYPE

FILE_RESPONSE = {200: {"content": {XLSX_TYPE: {"schema": {"type": "string", "format": "binary"}}}}}
UPLOAD_REQUEST = {"requestBody": {"required": True, "content": FILE_RESPONSE[200]["content"]}}


def throttle(database: Database, actor: AuditActor, operation: str) -> None:
    try:
        limit_workbooks(database, actor, operation)
    except WorkbookThrottled as exc:
        raise HTTPException(
            429, "Wait before making another workbook request.", headers={"Retry-After": "60"}
        ) from exc


def download(content: bytes, name: str) -> Response:
    return Response(
        content,
        media_type=XLSX_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="workforce-{name}.xlsx"',
            "X-Content-Type-Options": "nosniff",
        },
    )


async def read_upload(request: Request) -> bytes:
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != XLSX_TYPE:
        raise HTTPException(415, "Send an .xlsx workbook.")
    length = request.headers.get("content-length")
    if length and (
        not length.isascii()
        or not length.isdecimal()
        or len(length) > 7
        or int(length) > MAX_UPLOAD_BYTES
    ):
        raise HTTPException(413, "The workbook exceeds the 1 MiB upload limit.")
    content = bytearray()
    try:
        async for part in request.stream():
            if len(content) + len(part) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "The workbook exceeds the 1 MiB upload limit.")
            content.extend(part)
    except ClientDisconnect as exc:
        raise HTTPException(422, "Workbook upload did not complete.") from exc
    return bytes(content)
