"""HTTP adapter for room core; all object authorization lives in RoomService."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from . import models as m
from .service import RoomError, RoomService
from .quota import QuotaCircuit
from .rate_limit import RequestLimiter
from .store import FirestoreStore

SlugPath = Annotated[
    str, Path(min_length=3, max_length=48, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
]


class PrivateRoute(APIRoute):
    feature_enabled = staticmethod(lambda: True)

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request) -> Response:
            # Never echo invalid request bodies, bearer credentials, or invitation tokens.
            try:
                if not self.feature_enabled():
                    raise HTTPException(404, "Not found")
                if request.method == "POST":
                    if (
                        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                        != "application/json"
                    ):
                        raise HTTPException(415, "INVALID_CONTENT_TYPE")
                    size = 0
                    chunks = []
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > 16384:
                            raise HTTPException(413, "REQUEST_TOO_LARGE")
                        chunks.append(chunk)
                    body = b"".join(chunks)

                    async def receive():
                        return {"type": "http.request", "body": body, "more_body": False}

                    request = Request(request.scope, receive=receive)
                result = await handler(request)
            except RequestValidationError:
                result = JSONResponse({"detail": "INVALID_REQUEST"}, status_code=422)
            except RoomError as error:
                result = JSONResponse({"detail": error.code}, status_code=error.status)
            except HTTPException as error:
                result = JSONResponse(
                    {"detail": error.detail}, status_code=error.status_code, headers=error.headers
                )
            result.headers["Cache-Control"] = "no-store"
            result.headers["Referrer-Policy"] = "no-referrer"
            return result

        return handle


def make_room_router(
    identify, database_provider, enabled=lambda: True, *, on_change=None, circuit=None, limiter=None
):
    class EnabledRoute(PrivateRoute):
        feature_enabled = staticmethod(enabled)

    router = APIRouter(
        prefix="/sameplace",
        tags=["sameplace-room-core"],
        route_class=EnabledRoute,
        include_in_schema=False,
    )

    circuit = circuit if circuit is not None else QuotaCircuit()
    limiter = limiter if limiter is not None else RequestLimiter()

    def available():
        remaining = circuit.remaining()
        if remaining:
            raise HTTPException(503, "STORAGE_UNAVAILABLE", headers={"Retry-After": str(remaining)})

    def actor(request: Request, _available=Depends(available)):
        try:
            current = m.Actor.model_validate(identify(request))
            if request.method == "POST" and not limiter.allow(current.uid):
                raise HTTPException(429, "RATE_LIMIT", headers={"Retry-After": "60"})
            return current
        except Exception as exc:
            circuit.observe(exc)
            raise

    def service():
        try:
            database, transactional = database_provider()
            return RoomService(FirestoreStore(database, transactional))
        except Exception as exc:
            circuit.observe(exc)
            raise HTTPException(503, "STORAGE_UNAVAILABLE") from exc

    def run(callback):
        try:
            return callback()
        except RoomError:
            raise
        except Exception as exc:
            circuit.observe(exc)
            # No provider details, request payload or credentials returned.
            raise HTTPException(503, "STORAGE_UNAVAILABLE", headers={"Retry-After": "60"}) from exc

    @router.get("/identity")
    def identity(current=Depends(actor), rooms=Depends(service)):
        return run(lambda: rooms.identity(current))

    @router.get("/rooms")
    def list_rooms(current=Depends(actor), rooms=Depends(service)):
        return run(lambda: rooms.list_rooms(current))

    @router.post("/rooms")
    def create(command: m.CreateRoom, current=Depends(actor), rooms=Depends(service)):
        return run(lambda: rooms.create(current, command))

    @router.get("/rooms/{slug}")
    def get(slug: SlugPath, current=Depends(actor), rooms=Depends(service)):
        return run(lambda: rooms.get(current, slug))

    @router.post("/redeem")
    def redeem(command: m.Redeem, current=Depends(actor), rooms=Depends(service)):
        result = run(lambda: rooms.redeem(current, command))
        if on_change is not None:
            on_change("redeem", result, command)
        return result

    @router.post("/admin/approval")
    def approval(command: m.Approval, current=Depends(actor), rooms=Depends(service)):
        return run(lambda: rooms.approve(current, command))

    @router.post("/admin/limits")
    def limits(command: m.Limits, current=Depends(actor), rooms=Depends(service)):
        result = run(lambda: rooms.limits(current, command))
        if on_change is not None:
            on_change("limits", result, command)
        return result

    def register(action, model):
        # Register typed commands once; no arbitrary action names from the client.
        def endpoint(slug: SlugPath, command, current=Depends(actor), rooms=Depends(service)):
            result = run(lambda: rooms.change(current, slug, action, command))
            if on_change is not None:
                on_change(action, result, command)
            return result

        endpoint.__annotations__["command"] = model
        endpoint.__name__ = "room_" + action
        router.add_api_route("/rooms/{slug}/" + action, endpoint, methods=["POST"])

    for action, model in {
        "update": m.UpdateRoom,
        "design": m.DesignRoom,
        "archive": m.Versioned,
        "restore": m.Versioned,
        "roles": m.SetRoles,
        "block": m.MemberCommand,
        "remove": m.MemberCommand,
        "unblock": m.MemberCommand,
        "invite": m.Invite,
        "revoke_invite": m.RevokeInvite,
        "propose_transfer": m.MemberCommand,
        "cancel_transfer": m.Versioned,
        "accept_transfer": m.TransferAccept,
    }.items():
        register(action, model)
    return router
