"""Room application service. No HTTP, Firebase SDK, or website dependencies."""

import hashlib
import json
import secrets
import time
from collections.abc import Callable
from uuid import uuid4

from .store import Store

MAX_MEMBERS = 100
MAX_INVITES = 50
MAX_INDEX = 100
DEFAULT_LIMITS = {
    "storage_rooms": 100,
    "active_rooms": 4,
    "active_participants": 20,
    "capacity_ceiling": 10,
}


class RoomError(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
        super().__init__(code)


def deny():
    raise RoomError(404, "ROOM_NOT_FOUND")


def require(condition, status=403, code="ACCESS_DENIED"):
    if not condition:
        raise RoomError(status, code)


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def user_key(uid):
    return "user_" + hash_value(uid)


def room_key(room_id):
    return "room_" + room_id


def user(unit, uid):
    return unit.get(user_key(uid)) or {
        "schema_version": 1,
        "uid": uid,
        "approved": False,
        "owned": [],
        "rooms": [],
    }


def policy(unit):
    return unit.get("policy") or {"schema_version": 1, "limits": DEFAULT_LIMITS.copy(), "stored": 0}


def member(room, uid):
    item = room["members"].get(uid)
    return item if item and item["status"] == "active" else None


def can(room, uid, role):
    item = member(room, uid)
    return bool(item and (room["owner_uid"] == uid or role in item["roles"]))


def invalidate_issuer(room, uid):
    for invitation in room["invites"].values():
        if invitation["issuer"] == uid and invitation["status"] == "pending":
            invitation["status"] = "revoked"


def view(room, uid):
    """No invite digest, email, idempotency key, or hidden other-room state."""
    own = room["owner_uid"] == uid
    item = member(room, uid)
    result = {
        key: room[key]
        for key in (
            "id",
            "slug",
            "name",
            "capacity",
            "interior",
            "status",
            "version",
            "visibility",
            "location",
        )
    }
    result.update(
        {
            "is_owner": own,
            "roles": item["roles"] if item else [],
            "can_invite": can(room, uid, "inviter"),
            "can_moderate": can(room, uid, "moderator"),
        }
    )
    if own or can(room, uid, "moderator"):
        result["members"] = [
            {
                "uid": key,
                "roles": value["roles"],
                "status": value["status"],
                "owner": key == room["owner_uid"],
            }
            for key, value in sorted(room["members"].items())
        ]
    if can(room, uid, "inviter"):
        result["invites"] = [
            {"id": key, "expires_at_ms": value["expires_at_ms"], "status": value["status"]}
            for key, value in room["invites"].items()
            if own or value["issuer"] == uid
        ]
    transfer = room.get("transfer")
    if transfer and (own or transfer["target"] == uid):
        result["transfer"] = transfer.copy()
    return result


class RoomService:
    def __init__(self, store: Store, now: Callable[[], int] | None = None):
        self.store = store
        self.now = now or (lambda: int(time.time() * 1000))

    def _audit(self, unit, actor, action, subject, now, event_id):
        unit.set(
            "audit_" + event_id,
            {
                "schema_version": 1,
                "actor_uid": actor.uid,
                "action": action,
                "subject": subject,
                "at_ms": now,
            },
        )

    def _command(self, actor, action, subject, command, operation):
        now = self.now()
        event = uuid4().hex
        key = "command_" + hash_value(actor.uid + "\0" + command.request_id)
        fingerprint = hash_value(
            json.dumps([action, subject, command.model_dump()], sort_keys=True, ensure_ascii=True)
        )

        def execute(unit):
            previous = unit.get(key)
            if previous:
                require(previous["fingerprint"] == fingerprint, 409, "REQUEST_CONFLICT")
            result, changed = operation(unit, now, previous)
            if changed and not previous:
                # Never store plaintext invitation tokens or full projections in receipts.
                unit.set(
                    key,
                    {
                        "schema_version": 1,
                        "fingerprint": fingerprint,
                        "subject": result.get("id", subject),
                        "at_ms": now,
                    },
                )
                self._audit(unit, actor, action, result.get("id", subject), now, event)
            return result

        return self.store.run(execute)

    def authorized_room(self, unit, slug, actor):
        """Authorize an active room inside a caller-owned transaction."""
        return self._room(unit, slug, actor)

    def execute_command(self, actor, action, subject, command, operation):
        """Reuse the room-core durable receipt and audit mechanism."""
        return self._command(actor, action, subject, command, operation)

    def identity(self, actor):
        def read(unit):
            index = user(unit, actor.uid)
            return {
                "uid": actor.uid,
                "platform_owner": actor.platform_owner,
                "can_create": actor.platform_owner or index["approved"],
                "limits": policy(unit)["limits"],
            }

        return self.store.run(read)

    def list_rooms(self, actor):
        def read(unit):
            index = user(unit, actor.uid)
            rooms = []
            for room_id in index["rooms"]:
                room = unit.get(room_key(room_id))
                if (
                    room
                    and member(room, actor.uid)
                    and (room["status"] == "active" or room["owner_uid"] == actor.uid)
                ):
                    projected = view(room, actor.uid)
                    rooms.append(
                        {
                            key: projected[key]
                            for key in (
                                "id",
                                "slug",
                                "name",
                                "capacity",
                                "status",
                                "version",
                                "is_owner",
                            )
                        }
                    )
            return {
                "rooms": rooms,
                "can_create": actor.platform_owner or index["approved"],
                "platform_owner": actor.platform_owner,
                "uid": actor.uid,
            }

        return self.store.run(read)

    def get(self, actor, slug):
        return self.store.run(
            lambda unit: view(self._room(unit, slug, actor, archived=True), actor.uid)
        )

    def _room(self, unit, slug, actor, archived=False):
        mapping = unit.get("slug_" + slug)
        room = unit.get(room_key(mapping["id"])) if mapping else None
        if not room or not member(room, actor.uid):
            deny()
        if room["status"] != "active" and not (archived and room["owner_uid"] == actor.uid):
            deny()
        return room

    def approve(self, actor, command):
        require(actor.platform_owner)

        def execute(unit, now, previous):
            index = user(unit, command.uid)
            if previous:
                return {"approved": index["approved"]}, False
            index["approved"] = command.approved
            unit.set(user_key(command.uid), index)
            return {"approved": command.approved}, True

        return self._command(actor, "creator.approve", command.uid, command, execute)

    def limits(self, actor, command):
        require(actor.platform_owner)

        def execute(unit, now, previous):
            current = policy(unit)
            if previous:
                return {"limits": current["limits"]}, False
            proposed = command.model_dump(exclude={"request_id"})
            require(proposed["storage_rooms"] >= current["stored"], 409, "STORAGE_LIMIT")
            current["limits"] = proposed
            unit.set("policy", current)
            return {"limits": proposed}, True

        return self._command(actor, "policy.limits", "platform", command, execute)

    def create(self, actor, command):
        room_id = uuid4().hex

        def execute(unit, now, previous):
            index = user(unit, actor.uid)
            if previous:
                room = unit.get(room_key(previous["subject"]))
                if not room or not member(room, actor.uid):
                    deny()
                return view(room, actor.uid), False
            require(actor.platform_owner or index["approved"])
            current = policy(unit)
            require(len(index["owned"]) < 3, 409, "OWNER_LIMIT")
            require(len(index["rooms"]) < MAX_INDEX, 409, "MEMBERSHIP_LIMIT")
            require(current["stored"] < current["limits"]["storage_rooms"], 409, "STORAGE_LIMIT")
            require(
                command.capacity <= current["limits"]["capacity_ceiling"], 409, "CAPACITY_LIMIT"
            )
            require(unit.get("slug_" + command.slug) is None, 409, "SLUG_TAKEN")
            room = {
                "schema_version": 1,
                "id": room_id,
                "slug": command.slug,
                "name": command.name,
                "capacity": command.capacity,
                "interior": command.interior,
                "visibility": "private",
                "status": "active",
                "version": 1,
                "owner_uid": actor.uid,
                "location": {"id": "lounge", "kind": "lounge"},
                "members": {actor.uid: {"status": "active", "roles": []}},
                "invites": {},
                "transfer": None,
                "created_at_ms": now,
            }
            index["owned"].append(room_id)
            index["rooms"].append(room_id)
            current["stored"] += 1
            unit.set("policy", current)
            unit.set(user_key(actor.uid), index)
            unit.set("slug_" + command.slug, {"schema_version": 1, "id": room_id})
            unit.set(room_key(room_id), room)
            return view(room, actor.uid), True

        return self._command(actor, "room.create", command.slug, command, execute)

    def change(self, actor, slug, action, command):
        token = secrets.token_urlsafe(32)
        item_id = uuid4().hex

        def execute(unit, now, previous):
            room = self._room(unit, slug, actor, archived=True)
            owner = room["owner_uid"] == actor.uid
            if action in {"invite", "revoke_invite"}:
                require(can(room, actor.uid, "inviter"))
            elif action == "design":
                require(can(room, actor.uid, "designer"))
            elif action in {"block", "remove", "unblock"}:
                require(can(room, actor.uid, "moderator"))
            elif action == "accept_transfer":
                # Retry after successful transfer remains valid only for the new owner.
                require(
                    (room.get("transfer") or {}).get("target") == actor.uid or (previous and owner)
                )
            else:
                require(owner)
            if previous:
                return view(room, actor.uid), False
            require(room["version"] == command.version, 409, "STALE_VERSION")
            require(room["status"] == "active" or action == "restore", 409, "ROOM_ARCHIVED")
            result_extra = {}
            if action == "update":
                require(
                    command.capacity <= policy(unit)["limits"]["capacity_ceiling"],
                    409,
                    "CAPACITY_LIMIT",
                )
                room.update(name=command.name, capacity=command.capacity, interior=command.interior)
            elif action == "design":
                room["interior"] = command.interior
            elif action == "archive":
                index = user(unit, actor.uid)
                index["owned"].remove(room["id"])
                unit.set(user_key(actor.uid), index)
                room.update(status="archived", transfer=None)
                for invite in room["invites"].values():
                    if invite["status"] == "pending":
                        invite["status"] = "revoked"
            elif action == "restore":
                require(room["status"] == "archived", 409, "INVALID_STATE")
                index = user(unit, actor.uid)
                require(actor.platform_owner or index["approved"])
                require(len(index["owned"]) < 3, 409, "OWNER_LIMIT")
                require(
                    room["capacity"] <= policy(unit)["limits"]["capacity_ceiling"],
                    409,
                    "CAPACITY_LIMIT",
                )
                index["owned"].append(room["id"])
                unit.set(user_key(actor.uid), index)
                room["status"] = "active"
            elif action == "roles":
                require(
                    command.uid != room["owner_uid"] and member(room, command.uid),
                    409,
                    "INVALID_MEMBER",
                )
                room["members"][command.uid]["roles"] = command.roles
                if not can(room, command.uid, "inviter"):
                    invalidate_issuer(room, command.uid)
            elif action in {"block", "remove", "unblock"}:
                require(
                    command.uid != room["owner_uid"] and command.uid != actor.uid,
                    409,
                    "INVALID_MEMBER",
                )
                target = room["members"].get(command.uid)
                require(target and (owner or not target["roles"]), 403, "ACCESS_DENIED")
                require(action != "unblock" or target["status"] == "blocked", 409, "INVALID_MEMBER")
                target.update(
                    status="blocked" if action == "block" else "removed",
                    roles=[],
                    revoked_at_version=room["version"] + 1,
                )
                invalidate_issuer(room, command.uid)
                idx = user(unit, command.uid)
                if room["id"] in idx["rooms"]:
                    idx["rooms"].remove(room["id"])
                unit.set(user_key(command.uid), idx)
                if (room.get("transfer") or {}).get("target") == command.uid:
                    room["transfer"] = None
            elif action == "invite":
                room["invites"] = {
                    key: value
                    for key, value in room["invites"].items()
                    if value["expires_at_ms"] > now
                }
                require(len(room["invites"]) < MAX_INVITES, 409, "INVITE_LIMIT")
                raw = room["id"] + "." + token
                room["invites"][item_id] = {
                    "digest": hash_value(raw),
                    "target_kind": command.target_kind,
                    "target": hash_value(
                        command.target.casefold()
                        if command.target_kind == "email"
                        else command.target
                    ),
                    "issuer": actor.uid,
                    "issued_at_ms": now,
                    "issued_version": room["version"] + 1,
                    "expires_at_ms": now + command.days * 86400000,
                    "status": "pending",
                }
                result_extra = {"invitation_token": raw}
            elif action == "revoke_invite":
                invite = room["invites"].get(command.invite_id)
                require(
                    invite and (owner or invite["issuer"] == actor.uid), 404, "INVITE_NOT_FOUND"
                )
                invite["status"] = "revoked"
            elif action == "propose_transfer":
                require(
                    command.uid != actor.uid and member(room, command.uid), 409, "INVALID_MEMBER"
                )
                require(user(unit, command.uid)["approved"], 403, "CREATOR_REQUIRED")
                room["transfer"] = {
                    "id": item_id,
                    "target": command.uid,
                    "expires_at_ms": now + 86400000,
                }
            elif action == "cancel_transfer":
                room["transfer"] = None
            elif action == "accept_transfer":
                transfer = room.get("transfer")
                require(
                    transfer
                    and transfer["id"] == command.transfer_id
                    and transfer["expires_at_ms"] > now,
                    409,
                    "TRANSFER_INVALID",
                )
                incoming, outgoing = user(unit, actor.uid), user(unit, room["owner_uid"])
                require(actor.platform_owner or incoming["approved"], 403, "CREATOR_REQUIRED")
                require(len(incoming["owned"]) < 3, 409, "OWNER_LIMIT")
                outgoing["owned"].remove(room["id"])
                incoming["owned"].append(room["id"])
                old = room["owner_uid"]
                invalidate_issuer(room, old)
                room["members"][old]["roles"] = []
                room["members"][actor.uid]["roles"] = []
                unit.set(user_key(old), outgoing)
                unit.set(user_key(actor.uid), incoming)
                room.update(owner_uid=actor.uid, transfer=None)
            else:
                raise RoomError(404, "UNKNOWN_COMMAND")
            room["version"] += 1
            unit.set(room_key(room["id"]), room)
            return {**view(room, actor.uid), **result_extra}, True

        return self._command(actor, "room." + action, slug, command, execute)

    def redeem(self, actor, command):
        room_id = command.token.split(".")[0]

        def execute(unit, now, previous):
            room = unit.get(room_key(room_id))
            if not room or room["status"] != "active":
                deny()
            if previous:
                if not member(room, actor.uid):
                    deny()
                return view(room, actor.uid), False
            digest = hash_value(command.token)
            invite = next(
                (
                    value
                    for value in room["invites"].values()
                    if secrets.compare_digest(value["digest"], digest)
                ),
                None,
            )
            require(
                invite
                and invite["status"] == "pending"
                and invite["expires_at_ms"] > now
                and can(room, invite["issuer"], "inviter"),
                404,
                "INVITE_INVALID",
            )
            target = (
                actor.uid
                if invite["target_kind"] == "uid"
                else (actor.verified_email or "").casefold()
            )
            require(
                bool(target) and secrets.compare_digest(hash_value(target), invite["target"]),
                404,
                "INVITE_INVALID",
            )
            existing = room["members"].get(actor.uid)
            require(
                not existing
                or (
                    existing["status"] != "blocked"
                    and invite["issued_version"] > existing.get("revoked_at_version", -1)
                ),
                404,
                "INVITE_INVALID",
            )
            index = user(unit, actor.uid)
            if not member(room, actor.uid):
                require(
                    len(room["members"]) < MAX_MEMBERS or existing is not None,
                    409,
                    "MEMBERSHIP_LIMIT",
                )
                require(len(index["rooms"]) < MAX_INDEX, 409, "MEMBERSHIP_LIMIT")
                room["members"][actor.uid] = {"status": "active", "roles": []}
                if room_id not in index["rooms"]:
                    index["rooms"].append(room_id)
                unit.set(user_key(actor.uid), index)
            invite["status"] = "consumed"
            room["version"] += 1
            unit.set(room_key(room_id), room)
            return view(room, actor.uid), True

        return self._command(actor, "invite.redeem", room_id, command, execute)
