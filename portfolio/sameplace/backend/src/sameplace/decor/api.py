"""Room-scoped transport with existing quota and verified identity adapters."""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..rooms.api import PrivateRoute, SlugPath
from ..rooms.models import Actor
from ..rooms.rate_limit import RequestLimiter
from ..rooms.service import RoomError
from ..rooms.store import FirestoreStore
from .models import DeleteTemplate, MusicCommand, PublishScene, SaveTemplate
from .service import DecorService


def make_decor_router(identify, database_provider, enabled, hub, circuit, limiter):
    class EnabledRoute(PrivateRoute):
        feature_enabled = staticmethod(enabled)

    router = APIRouter(prefix="/sameplace", route_class=EnabledRoute, include_in_schema=False)
    reads = RequestLimiter()

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

    def actor(request: Request):
        remaining = circuit.remaining()
        if remaining:
            raise HTTPException(503, "STORAGE_UNAVAILABLE", headers={"Retry-After": str(remaining)})
        current = run(lambda: Actor.model_validate(identify(request)))
        if not (limiter if request.method == "POST" else reads).allow(current.uid):
            raise HTTPException(429, "RATE_LIMIT", headers={"Retry-After": "60"})
        return current

    def service():
        def build():
            db, transactional = database_provider()
            return DecorService(FirestoreStore(db, transactional))

        return run(build)

    @router.get("/rooms/{slug}/decor")
    def get(slug: SlugPath, current=Depends(actor), decor=Depends(service)):
        return run(lambda: decor.get(current, slug))

    @router.post("/rooms/{slug}/decor/publish")
    def publish(
        slug: SlugPath, command: PublishScene, current=Depends(actor), decor=Depends(service)
    ):
        result = run(lambda: decor.publish(current, slug, command))
        hub.fence(slug)
        return result

    @router.post("/rooms/{slug}/decor/save_template")
    def save(slug: SlugPath, command: SaveTemplate, current=Depends(actor), decor=Depends(service)):
        return run(lambda: decor.template(current, slug, command))

    @router.post("/rooms/{slug}/decor/delete_template")
    def delete(
        slug: SlugPath, command: DeleteTemplate, current=Depends(actor), decor=Depends(service)
    ):
        return run(lambda: decor.template(current, slug, command, delete=True))

    @router.post("/rooms/{slug}/decor/music")
    def music(
        slug: SlugPath, command: MusicCommand, current=Depends(actor), decor=Depends(service)
    ):
        result = run(lambda: decor.music(current, slug, command))
        hub.fence(slug)
        return result

    return router
