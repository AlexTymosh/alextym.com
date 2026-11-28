"""Versioned scene and audio state; no audio transport or game dependencies."""

from copy import deepcopy
from uuid import uuid4

from ..rooms.service import RoomService, can, hash_value, require
from ..social.service import public_id
from .catalog import catalogue, preset
from .sources import sources

MAX_TEMPLATES = 12


def default_music(registry):
    return {
        "revision": 0,
        "source_id": "melodia_disco" if registry["melodia_disco"]["available"] else "test_disco",
        "playback": "playing" if registry["melodia_disco"]["available"] else "stopped",
        "position_ms": 0,
        "started_at_ms": 0,
        "changed_by": None,
    }


def position(state, source, now):
    duration = source.get("duration_ms")
    if not duration:
        return 0
    elapsed = max(0, now - state["started_at_ms"]) if state["playback"] == "playing" else 0
    return (state["position_ms"] + elapsed) % duration


class DecorService:
    def __init__(self, store, now=None, registry=sources):
        self.store = store
        self.rooms = RoomService(store, now)
        self.registry = registry

    def _key(self, room):
        return "decor_" + room["id"]

    def _state(self, unit, room, registry):
        saved = unit.get(self._key(room)) or {
            "schema_version": 1,
            "scenes": {},
            "music": {},
            "music_versions": {},
        }
        state = deepcopy(saved)
        for location in ("lounge", "table"):
            state["scenes"].setdefault(location, {"revision": 0, "scene": preset(room["interior"])})
        state["music"].setdefault("room", default_music(registry))
        return state

    def _library_key(self, actor):
        return "scene_library_" + hash_value(actor.uid)

    def _library(self, unit, actor):
        return unit.get(self._library_key(actor)) or {"schema_version": 1, "templates": []}

    def _view(self, unit, room, actor, registry, now):
        state = self._state(unit, room, registry)
        designer = can(room, actor.uid, "designer")
        return {
            "id": room["id"],
            "room_version": room["version"],
            "can_design": designer,
            "can_dj": can(room, actor.uid, "dj"),
            "scenes": state["scenes"],
            "music": state["music"],
            "music_versions": state["music_versions"],
            "sources": registry,
            "catalogue": catalogue(),
            "templates": self._library(unit, actor)["templates"] if designer else [],
            "server_now_ms": now,
        }

    def get(self, actor, slug):
        registry, now = self.registry(), self.rooms.now()
        return self.store.run(
            lambda unit: self._view(
                unit, self.rooms.authorized_room(unit, slug, actor), actor, registry, now
            )
        )

    def publish(self, actor, slug, command):
        registry = self.registry()

        def execute(unit, now, previous):
            room = self.rooms.authorized_room(unit, slug, actor)
            require(can(room, actor.uid, "designer"))
            if previous:
                return self._view(unit, room, actor, registry, now), False
            state = self._state(unit, room, registry)
            require(
                command.room_version == room["version"]
                and command.revision == state["scenes"][command.location]["revision"],
                409,
                "SCENE_CONFLICT",
            )
            state["scenes"][command.location] = {
                "revision": command.revision + 1,
                "scene": command.scene.model_dump(),
            }
            # Do not persist fallback scenes that have never been published.
            state["scenes"] = {
                key: value for key, value in state["scenes"].items() if value["revision"] > 0
            }
            unit.set(self._key(room), state)
            return self._view(unit, room, actor, registry, now), True

        return self.rooms.execute_command(actor, "decor.publish", slug, command, execute)

    def template(self, actor, slug, command, delete=False):
        registry = self.registry()
        identifier = uuid4().hex

        def execute(unit, now, previous):
            room = self.rooms.authorized_room(unit, slug, actor)
            require(can(room, actor.uid, "designer"))
            if previous:
                return self._view(unit, room, actor, registry, now), False
            library = self._library(unit, actor)
            items = library["templates"]
            existing = next((item for item in items if item["id"] == command.template_id), None)
            if delete:
                require(
                    existing and existing["revision"] == command.revision, 409, "SCENE_CONFLICT"
                )
                items.remove(existing)
            elif command.template_id:
                require(
                    existing and existing["revision"] == command.revision, 409, "SCENE_CONFLICT"
                )
                existing.update(
                    name=command.name,
                    scene=command.scene.model_dump(),
                    revision=existing["revision"] + 1,
                    updated_at_ms=now,
                )
            else:
                require(command.revision == 0 and len(items) < MAX_TEMPLATES, 409, "TEMPLATE_LIMIT")
                items.append(
                    {
                        "id": identifier,
                        "revision": 1,
                        "name": command.name,
                        "scene": command.scene.model_dump(),
                        "updated_at_ms": now,
                    }
                )
            unit.set(self._library_key(actor), library)
            return self._view(unit, room, actor, registry, now), True

        return self.rooms.execute_command(
            actor,
            "decor.delete_template" if delete else "decor.save_template",
            slug,
            command,
            execute,
        )

    def music(self, actor, slug, command):
        registry = self.registry()

        def execute(unit, now, previous):
            room = self.rooms.authorized_room(unit, slug, actor)
            require(can(room, actor.uid, "dj"))
            if previous:
                return self._view(unit, room, actor, registry, now), False
            state = self._state(unit, room, registry)
            scope = command.scope
            current = state["music"].get(scope)
            revision = state["music_versions"].get(scope, 0)
            require(command.revision == revision, 409, "MUSIC_CONFLICT")
            if command.action == "inherit":
                state["music"].pop(scope, None)
            else:
                current = deepcopy(current or state["music"]["room"])
                source = registry.get(current["source_id"], {})
                current["position_ms"] = position(current, source, now)
                action = command.action
                if action == "select":
                    source = registry.get(command.source_id)
                    require(source and source["available"], 409, "SOURCE_UNAVAILABLE")
                    current.update(source_id=command.source_id, position_ms=0)
                elif action == "seek":
                    require(
                        source.get("mode") == "recorded"
                        and source.get("duration_ms")
                        and command.position_ms < source["duration_ms"],
                        409,
                        "INVALID_SEEK",
                    )
                    current["position_ms"] = command.position_ms
                elif action == "play":
                    require(source.get("available"), 409, "SOURCE_UNAVAILABLE")
                    current["playback"] = "playing"
                elif action == "pause":
                    current["playback"] = "paused"
                elif action == "stop":
                    current.update(playback="stopped", position_ms=0)
                current.update(
                    revision=revision + 1, started_at_ms=now, changed_by=public_id(actor.uid)
                )
                state["music"][scope] = current
            state["music_versions"][scope] = revision + 1
            state["scenes"] = {
                key: value for key, value in state["scenes"].items() if value["revision"] > 0
            }
            unit.set(self._key(room), state)
            return self._view(unit, room, actor, registry, now), True

        return self.rooms.execute_command(actor, "decor.music", slug, command, execute)
