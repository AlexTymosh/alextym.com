"""HTTP and WebSocket adapters. Core and social share one bounded quota circuit."""

import asyncio
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from ..rooms.api import PrivateRoute, SlugPath
from ..rooms.models import Actor
from ..rooms.rate_limit import RequestLimiter
from ..rooms.service import RoomError, require
from ..rooms.store import FirestoreStore
from . import models as m
from .hub import AUTH_SECONDS
from .service import SocialService


async def send_frame(socket, frame):
    await asyncio.wait_for(socket.send_json(frame), 5)


async def receive_frame(socket):
    raw = await socket.receive_text()
    if len(raw) > 1024:
        raise ValueError("Oversized frame")
    frame = json.loads(raw)
    if not isinstance(frame, dict):
        raise ValueError("Invalid frame")
    return frame


def make_social_router(
    identify, database_provider, enabled, realtime_enabled, allowed_origin, hub, circuit, limiter
):
    class EnabledRoute(PrivateRoute):
        feature_enabled = staticmethod(enabled)

    router = APIRouter(prefix="/sameplace", route_class=EnabledRoute, include_in_schema=False)

    read_limiter = RequestLimiter()

    def available():
        remaining = circuit.remaining()
        if remaining:
            raise HTTPException(503, "STORAGE_UNAVAILABLE", headers={"Retry-After": str(remaining)})

    def run(callback):
        try:
            return callback()
        except (RoomError, HTTPException):
            raise
        except Exception as error:
            circuit.observe(error)
            raise HTTPException(
                503, "STORAGE_UNAVAILABLE", headers={"Retry-After": "60"}
            ) from error

    def actor(request: Request, _available=Depends(available)):
        try:
            current = Actor.model_validate(identify(request))
            selected_limiter = limiter if request.method == "POST" else read_limiter
            if not selected_limiter.allow(current.uid):
                raise HTTPException(429, "RATE_LIMIT", headers={"Retry-After": "60"})
            return current
        except Exception as error:
            circuit.observe(error)
            raise

    def service():
        def build():
            db, transactional = database_provider()
            return SocialService(FirestoreStore(db, transactional), hub)

        return run(build)

    @router.get("/social/me")
    def me(current=Depends(actor), social=Depends(service)):
        return run(lambda: social.me(current))

    @router.post("/social/profile")
    def profile(command: m.Profile, current=Depends(actor), social=Depends(service)):
        return run(lambda: social.set_profile(current, command))

    @router.post("/social/friend")
    def friend(command: m.Friend, current=Depends(actor), social=Depends(service)):
        return run(lambda: social.friend(current, command))

    @router.post("/social/read_notice")
    def read_notice(command: m.NoticeRead, current=Depends(actor), social=Depends(service)):
        return run(lambda: social.read_notice(current, command))

    @router.get("/rooms/{slug}/chat")
    def chat(slug: SlugPath, current=Depends(actor), social=Depends(service)):
        return run(lambda: social.chat(current, slug))

    @router.post("/rooms/{slug}/chat/page")
    def chat_page(
        slug: SlugPath, command: m.ChatPage, current=Depends(actor), social=Depends(service)
    ):
        return run(lambda: social.chat(current, slug, command.before))

    @router.post("/rooms/{slug}/chat/send")
    def chat_send(
        slug: SlugPath, command: m.ChatSend, current=Depends(actor), social=Depends(service)
    ):
        return run(lambda: social.send(current, slug, command))

    @router.post("/rooms/{slug}/chat/hide")
    def chat_hide(
        slug: SlugPath, command: m.ChatHide, current=Depends(actor), social=Depends(service)
    ):
        return run(lambda: social.hide(current, slug, command))

    @router.post("/rooms/{slug}/chat/cleanup")
    def chat_cleanup(
        slug: SlugPath, command: m.Model, current=Depends(actor), social=Depends(service)
    ):
        return run(lambda: social.cleanup_chat(current, slug))

    @router.post("/rooms/{slug}/favourite")
    def favourite(
        slug: SlugPath, command: m.Favourite, current=Depends(actor), social=Depends(service)
    ):
        return run(lambda: social.favourite(current, slug, command))

    @router.get("/rooms/{slug}/recipients")
    def recipients(slug: SlugPath, current=Depends(actor), social=Depends(service)):
        return run(lambda: social.recipients(current, slug))

    @router.post("/rooms/{slug}/ping")
    def ping(slug: SlugPath, command: m.Ping, current=Depends(actor), social=Depends(service)):
        return run(lambda: social.ping(current, slug, command))

    def register(action, model):
        def endpoint(slug: SlugPath, command, current=Depends(actor), social=Depends(service)):
            if not realtime_enabled():
                raise HTTPException(503, "REALTIME_DISABLED")
            return run(lambda: social.location(current, slug, action, command))

        endpoint.__annotations__["command"] = model
        endpoint.__name__ = "location_" + action
        router.add_api_route("/rooms/{slug}/location/" + action, endpoint, methods=["POST"])

    for action, model in {
        "propose": m.Proposal,
        "answer": m.ProposalAnswer,
        "cancel": m.ProposalCancel,
        "move": m.Move,
    }.items():
        register(action, model)

    @router.post("/rooms/{slug}/ticket")
    def ticket(
        slug: SlugPath,
        command: m.TicketRequest,
        request: Request,
        current=Depends(actor),
        social=Depends(service),
    ):
        if not realtime_enabled():
            raise HTTPException(503, "REALTIME_DISABLED")
        if not allowed_origin(command.origin):
            raise HTTPException(403, "ACCESS_DENIED")
        run(lambda: social.access(current, slug))
        authorization = request.headers.get("authorization", "")
        return {
            "ticket": hub.issue(current.uid, slug, command.origin, authorization),
            "protocol_version": 1,
        }

    def authorize(ticket):
        available()
        if not enabled() or not realtime_enabled() or not allowed_origin(ticket.origin):
            raise RoomError(403, "REALTIME_REVOKED")
        # The credential was independently verified at ticket issuance, but
        # current identity admission and room membership must be verified again.
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/sameplace/realtime",
                "headers": [(b"authorization", ticket.authorization.encode("latin-1"))],
            }
        )
        try:
            current = Actor.model_validate(identify(request))
            require(current.uid == ticket.uid)
            social = service()
            access = run(lambda: social.access(current, ticket.slug))
            return current, social, access
        except Exception as error:
            circuit.observe(error)
            raise

    @router.websocket("/realtime")
    async def realtime(socket: WebSocket):
        origin = socket.headers.get("origin", "")
        if (
            not enabled()
            or not realtime_enabled()
            or socket.url.query
            or not allowed_origin(origin)
        ):
            await socket.close(code=4403)
            return
        if not hub.begin_handshake():
            await socket.close(code=1013)
            return
        handshake = True
        ticket = None
        connection = None
        reader = None
        accepted = False
        try:
            await socket.accept()
            accepted = True
            first = await asyncio.wait_for(receive_frame(socket), 5)
            secret = first.get("ticket")
            if (
                set(first) != {"type", "ticket"}
                or first.get("type") != "auth"
                or not isinstance(secret, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{43}", secret)
            ):
                raise RoomError(403, "TICKET_INVALID")
            ticket = hub.consume(secret, origin)
            epoch = hub.version()
            current, social, access = await run_in_threadpool(authorize, ticket)
            connection = hub.admit(ticket, access, epoch)
            await run_in_threadpool(social.visit, current, ticket.slug)
            hub.end_handshake()
            handshake = False
            last_auth = hub.clock()
            last = None
            reader = asyncio.create_task(receive_frame(socket))
            while enabled() and realtime_enabled():
                if not hub.alive(ticket.slug, ticket.uid, connection):
                    raise RoomError(403, "REALTIME_REVOKED")
                if circuit.remaining():
                    raise RoomError(503, "STORAGE_UNAVAILABLE")
                if hub.clock() - last_auth >= AUTH_SECONDS:
                    await run_in_threadpool(authorize, ticket)
                    last_auth = hub.clock()
                snapshot = hub.snapshot(ticket.slug, ticket.uid, connection)
                revision = (snapshot["sequence"], snapshot["inbox_revision"])
                if revision != last:
                    await send_frame(socket, snapshot)
                    last = revision
                done, _ = await asyncio.wait({reader}, timeout=1)
                if done:
                    frame = reader.result()
                    if frame != {"type": "ping"} or not hub.ping(
                        ticket.slug, ticket.uid, connection
                    ):
                        raise RoomError(403, "INVALID_FRAME")
                    await send_frame(socket, {"type": "pong"})
                    reader = asyncio.create_task(receive_frame(socket))
            raise RoomError(503, "REALTIME_DISABLED")
        except WebSocketDisconnect:
            pass
        except (RoomError, HTTPException) as error:
            code = error.code if isinstance(error, RoomError) else str(error.detail)
            status = error.status if isinstance(error, RoomError) else error.status_code
            if accepted:
                try:
                    await send_frame(
                        socket,
                        {
                            "type": "error",
                            "code": code
                            if re.fullmatch(r"[A-Z_]{3,50}", code)
                            else "REALTIME_UNAVAILABLE",
                        },
                    )
                    await socket.close(
                        code=4403
                        if status in {401, 403, 404}
                        else 4409
                        if status in {409, 429}
                        else 1013
                    )
                except (RuntimeError, WebSocketDisconnect, TimeoutError):
                    pass
        except (ValueError, RuntimeError, TimeoutError, TypeError):
            if accepted:
                try:
                    await socket.close(code=4400)
                except (RuntimeError, WebSocketDisconnect):
                    pass
        except Exception as error:
            circuit.observe(error)
            if accepted:
                try:
                    await send_frame(socket, {"type": "error", "code": "REALTIME_UNAVAILABLE"})
                    await socket.close(code=1013)
                except (RuntimeError, WebSocketDisconnect, TimeoutError):
                    pass
        finally:
            if handshake:
                hub.end_handshake()
            if reader:
                reader.cancel()
                await asyncio.gather(reader, return_exceptions=True)
            if ticket and connection:
                hub.leave(ticket.slug, ticket.uid, connection)

    return router
