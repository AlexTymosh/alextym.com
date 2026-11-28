"""Durable social application service; room authorization is reused transactionally."""

import json
from uuid import uuid4
from ..rooms.service import RoomService, require, member, can, user, policy, room_key, hash_value
from .models import Privacy

DAY = 86400000
CHAT_RETENTION = 30 * DAY
MAX_CHAT_BYTES = 400000
MAX_CHAT = 500
MAX_FRIENDS = 40
MAX_NOTICES = 50


def public_id(uid):
    return hash_value("sameplace-public-v1\0" + uid)[:32]


def profile_key(uid):
    return "social_" + hash_value(uid)


def profile(unit, uid):
    return unit.get(profile_key(uid)) or {
        "schema_version": 1,
        "uid": uid,
        "public_id": public_id(uid),
        "nickname": "",
        "avatar": "initials",
        "privacy": Privacy().model_dump(),
        "friends": {},
        "favourites": [],
        "recent": [],
        "inbox": [],
        "pings": [],
    }


def save(unit, value):
    unit.set(profile_key(value["uid"]), value)
    key = "public_" + value["public_id"]
    mapping = unit.get(key)
    require(mapping is None or mapping["uid"] == value["uid"], 409, "PROFILE_CONFLICT")
    if mapping is None:
        unit.set(key, {"schema_version": 1, "uid": value["uid"]})


def public(value):
    return {key: value[key] for key in ("public_id", "nickname", "avatar")}


def blocked(left, right):
    return left["friends"].get(right["uid"]) in {"blocked", "blocked_by"} or right["friends"].get(
        left["uid"]
    ) in {"blocked", "blocked_by"}


def may_ping(sender, recipient, channel):
    if blocked(sender, recipient):
        return False
    friends = (
        sender["friends"].get(recipient["uid"])
        == recipient["friends"].get(sender["uid"])
        == "accepted"
    )
    privacy = recipient["privacy"]
    if not privacy["allow_friend_invites" if friends else "allow_nonfriend_invites"]:
        return False
    return (
        channel == "internal"
        or privacy["allow_email_pings" if channel == "email" else "allow_sms_pings"]
    )


class SocialService:
    def __init__(self, store, hub, now=None):
        self.store = store
        self.hub = hub
        self.rooms = RoomService(store, now)
        self.now = self.rooms.now

    def _scope(self, unit, actor):
        index = user(unit, actor.uid)
        require(
            actor.platform_owner
            or index["approved"]
            or bool(index["rooms"])
            or unit.get(profile_key(actor.uid)) is not None,
            403,
            "ACCESS_DENIED",
        )
        return profile(unit, actor.uid)

    def _room(self, unit, actor, slug):
        # Same SP02 authorization, in the same transaction as the social write.
        return self.rooms.authorized_room(unit, slug, actor)

    def _command(self, actor, action, subject, command, execute):
        return self.rooms.execute_command(actor, "social." + action, subject, command, execute)

    def access(self, actor, slug):
        def read(unit):
            room = self._room(unit, actor, slug)
            return {
                "room": {k: room[k] for k in ("id", "slug", "status", "capacity")},
                "media_permission": {
                    "channel": can(room, actor.uid, "organizer")
                    or can(room, actor.uid, "moderator"),
                    "moderate": can(room, actor.uid, "moderator"),
                    "owner": room["owner_uid"] == actor.uid,
                    "owner_uid": room["owner_uid"],
                },
                "limits": policy(unit)["limits"],
                "profile": public_profile(unit, actor.uid),
            }

        return self.store.run(read)

    def visit(self, actor, slug):
        def update(unit):
            room = self._room(unit, actor, slug)
            old = unit.get(profile_key(actor.uid))
            person = old or profile(unit, actor.uid)
            recent = [room["id"]] + [r for r in person["recent"] if r != room["id"]]
            recent = recent[:10]
            if old is None or recent != person["recent"]:
                person["recent"] = recent
                save(unit, person)

        self.store.run(update)

    def me(self, actor):
        now = self.now()

        def read(unit):
            person = self._scope(unit, actor)
            friends = []
            for uid, status in person["friends"].items():
                if status == "blocked_by":
                    continue
                other = profile(unit, uid)
                item = {**public(other), "status": status, "presence": "hidden"}
                if (
                    status == "accepted"
                    and other["friends"].get(actor.uid) == "accepted"
                    and not blocked(person, other)
                    and other["privacy"]["show_online"]
                ):
                    slug, seen = self.hub.presence(uid)
                    item["presence"] = "online" if slug else "not_in_meeting"
                    if slug and other["privacy"]["show_room"]:
                        mapping = unit.get("slug_" + slug)
                        room = unit.get(room_key(mapping["id"])) if mapping else None
                        if (
                            room
                            and room["status"] == "active"
                            and member(room, actor.uid)
                            and member(room, uid)
                        ):
                            item["room"] = {"slug": slug, "name": room["name"]}
                    if not slug and seen is not None and other["privacy"]["show_last_seen"]:
                        item["last_seen_ms"] = seen
                friends.append(item)
            index = user(unit, actor.uid)
            room_ids = set(index["rooms"])
            favourites = [r for r in person["favourites"] if r in room_ids]
            recent = [r for r in person["recent"] if r in room_ids]
            notices = []
            for notice in person["inbox"]:
                if notice["expires_at_ms"] <= now or notice["room_id"] not in room_ids:
                    continue
                room = unit.get(room_key(notice["room_id"]))
                if (
                    not room
                    or room["status"] != "active"
                    or not member(room, actor.uid)
                    or not member(room, notice["sender_uid"])
                ):
                    continue
                sender = profile(unit, notice["sender_uid"])
                if blocked(person, sender):
                    continue
                notices.append(
                    {k: v for k, v in notice.items() if k not in {"sender_uid", "room_id"}}
                )
            return {
                **public(person),
                "privacy": person["privacy"],
                "friends": friends,
                "favourites": favourites,
                "recent": recent,
                "notices": notices,
            }

        return self.store.run(read)

    def set_profile(self, actor, command):
        def execute(unit, now, previous):
            person = self._scope(unit, actor)
            if previous:
                return {**public(person), "privacy": person["privacy"]}, False
            person.update(
                nickname=command.nickname,
                avatar=command.avatar,
                privacy=command.privacy.model_dump(),
            )
            save(unit, person)
            return {**public(person), "privacy": person["privacy"]}, True

        result = self._command(actor, "profile", actor.uid, command, execute)
        self.hub.profile_changed(actor.uid, result)
        return result

    def friend(self, actor, command):
        def execute(unit, now, previous):
            left = self._scope(unit, actor)
            mapping = unit.get("public_" + command.target)
            require(mapping and mapping["uid"] != actor.uid, 404, "PROFILE_NOT_FOUND")
            right = profile(unit, mapping["uid"])
            uid = right["uid"]
            old, reciprocal = left["friends"].get(uid), right["friends"].get(actor.uid)
            if previous:
                return {"status": old or "none", "target_uid": uid}, False
            action = command.action
            if action == "block":
                if old == "blocked_by":
                    # Both can independently block; neither can undo the other's block.
                    left["friends"][uid] = "blocked"
                    right["friends"][actor.uid] = "blocked"
                elif old != "blocked":
                    require(
                        uid in left["friends"] or len(left["friends"]) < MAX_FRIENDS,
                        409,
                        "FRIEND_LIMIT",
                    )
                    require(
                        actor.uid in right["friends"] or len(right["friends"]) < MAX_FRIENDS,
                        409,
                        "FRIEND_LIMIT",
                    )
                    left["friends"][uid], right["friends"][actor.uid] = "blocked", "blocked_by"
            elif action == "unblock":
                require(old == "blocked", 409, "FRIEND_STATE")
                if reciprocal == "blocked":
                    left["friends"][uid] = "blocked_by"
                else:
                    left["friends"].pop(uid, None)
                    right["friends"].pop(actor.uid, None)
            else:
                require(not blocked(left, right), 404, "PROFILE_NOT_FOUND")
                if action == "request":
                    require(old is None and reciprocal is None, 409, "FRIEND_STATE")
                    require(
                        len(left["friends"]) < MAX_FRIENDS and len(right["friends"]) < MAX_FRIENDS,
                        409,
                        "FRIEND_LIMIT",
                    )
                    left["friends"][uid], right["friends"][actor.uid] = "outgoing", "incoming"
                elif action == "accept":
                    require(old == "incoming" and reciprocal == "outgoing", 409, "FRIEND_STATE")
                    left["friends"][uid] = right["friends"][actor.uid] = "accepted"
                else:
                    expected = {"decline": "incoming", "cancel": "outgoing", "remove": "accepted"}[
                        action
                    ]
                    require(old == expected, 409, "FRIEND_STATE")
                    left["friends"].pop(uid, None)
                    right["friends"].pop(actor.uid, None)
            save(unit, left)
            save(unit, right)
            return {"status": left["friends"].get(uid, "none"), "target_uid": uid}, True

        result = self._command(actor, "friend", command.target, command, execute)
        # The recipient's inbox/social view is read on demand; no global broadcast.
        self.hub.notify([actor.uid, result.pop("target_uid")])
        return result

    def favourite(self, actor, slug, command):
        def execute(unit, now, previous):
            room = self._room(unit, actor, slug)
            person = profile(unit, actor.uid)
            if previous:
                return {"enabled": room["id"] in person["favourites"]}, False
            values = [r for r in person["favourites"] if r != room["id"]]
            if command.enabled:
                require(len(values) < 100, 409, "FAVOURITE_LIMIT")
                values.append(room["id"])
            person["favourites"] = values
            save(unit, person)
            return {"enabled": command.enabled}, True

        return self._command(actor, "favourite", slug, command, execute)

    def chat(self, actor, slug, before=None):
        now = self.now()

        def read(unit):
            room = self._room(unit, actor, slug)
            data = unit.get("chat_" + room["id"]) or {"messages": []}
            messages = data["messages"]
            if before:
                position = next((i for i, m in enumerate(messages) if m["id"] == before), None)
                require(position is not None, 409, "CURSOR_EXPIRED")
                messages = messages[:position]
            visible = [m for m in messages if m["expires_at_ms"] > now and not m.get("hidden")]
            page = visible[-50:]
            return {
                "messages": [
                    {k: m[k] for k in ("id", "sender", "nickname", "text", "created_at_ms")}
                    for m in page
                ],
                "before": page[0]["id"] if len(visible) > len(page) else None,
            }

        return self.store.run(read)

    def send(self, actor, slug, command):
        identifier = uuid4().hex

        def execute(unit, now, previous):
            room = self._room(unit, actor, slug)
            require(self.hub.in_room(slug, actor.uid), 409, "JOIN_MEETING_REQUIRED")
            if previous:
                return {"id": previous["subject"]}, False
            key = "chat_" + room["id"]
            data = unit.get(key) or {"schema_version": 1, "messages": []}
            messages = [m for m in data["messages"] if m["expires_at_ms"] > now]
            # Durable per-author rate bound, independent of browser tabs/restart.
            require(
                sum(
                    m["sender"] == public_id(actor.uid) and m["created_at_ms"] > now - 60000
                    for m in messages
                )
                < 12,
                429,
                "RATE_LIMIT",
            )
            person = profile(unit, actor.uid)
            messages.append(
                {
                    "id": identifier,
                    "sender": person["public_id"],
                    "nickname": person["nickname"],
                    "text": command.text,
                    "created_at_ms": now,
                    "expires_at_ms": now + CHAT_RETENTION,
                }
            )
            require(
                len(messages) <= MAX_CHAT
                and len(json.dumps(messages, ensure_ascii=False).encode()) <= MAX_CHAT_BYTES,
                409,
                "CHAT_LIMIT",
            )
            data["messages"] = messages
            unit.set(key, data)
            return {"id": identifier}, True

        result = self._command(actor, "chat.send", slug, command, execute)
        self.hub.chat_changed(slug)
        return result

    def hide(self, actor, slug, command):
        def execute(unit, now, previous):
            room = self._room(unit, actor, slug)
            key = "chat_" + room["id"]
            data = unit.get(key) or {"schema_version": 1, "messages": []}
            item = next(
                (
                    m
                    for m in data["messages"]
                    if m["id"] == command.message_id and m["expires_at_ms"] > now
                ),
                None,
            )
            require(item is not None, 404, "MESSAGE_NOT_FOUND")
            own = item["sender"] == public_id(actor.uid)
            require(
                own or (can(room, actor.uid, "moderator") and command.reason), 403, "ACCESS_DENIED"
            )
            if previous or item.get("hidden"):
                return {"ok": True}, False
            item.update(hidden=True, text="", reason=command.reason if not own else "")
            unit.set(key, data)
            return {"ok": True}, True

        result = self._command(actor, "chat.hide", slug, command, execute)
        self.hub.chat_changed(slug)
        return result

    def cleanup_chat(self, actor, slug):
        now = self.now()

        def execute(unit):
            room = self._room(unit, actor, slug)
            require(can(room, actor.uid, "moderator"))
            key = "chat_" + room["id"]
            data = unit.get(key)
            if not data:
                return {"removed": 0}
            old = len(data["messages"])
            data["messages"] = [m for m in data["messages"] if m["expires_at_ms"] > now]
            removed = old - len(data["messages"])
            if removed:
                unit.set(key, data)
            return {"removed": removed}

        return self.store.run(execute)

    def recipients(self, actor, slug):
        def read(unit):
            room = self._room(unit, actor, slug)
            sender = profile(unit, actor.uid)
            result = []
            for uid in room["members"]:
                if uid == actor.uid or not member(room, uid):
                    continue
                other = profile(unit, uid)
                if blocked(sender, other):
                    continue
                result.append(
                    {
                        **public(other),
                        "channels": [
                            c for c in ("internal", "email", "sms") if may_ping(sender, other, c)
                        ],
                    }
                )
            return {"recipients": result}

        return self.store.run(read)

    def ping(self, actor, slug, command):
        identifier = uuid4().hex

        def execute(unit, now, previous):
            room = self._room(unit, actor, slug)
            require(self.hub.in_room(slug, actor.uid), 409, "JOIN_MEETING_REQUIRED")
            sender = profile(unit, actor.uid)
            members = {
                public_id(uid): uid
                for uid in room["members"]
                if uid != actor.uid and member(room, uid)
            }
            require(set(command.recipients) <= set(members), 403, "ACCESS_DENIED")
            targets = [profile(unit, members[key]) for key in command.recipients]
            require(
                all(may_ping(sender, target, command.channel) for target in targets),
                403,
                "NOTIFICATION_CONSENT",
            )
            if previous:
                return {
                    "status": "queued" if command.channel == "internal" else "disabled",
                    "target_uids": [target["uid"] for target in targets],
                }, False
            if command.channel != "internal":
                # No provider, contact lookup or billable effect. UI offers preview/copy.
                return {"status": "disabled"}, False
            pings = [p for p in sender["pings"] if p["at_ms"] > now - 600000]
            require(
                len(pings) < 3
                and not any(
                    p["room_id"] == room["id"] and set(p["recipients"]) & set(command.recipients)
                    for p in pings
                ),
                429,
                "RATE_LIMIT",
            )
            for target in targets:
                inbox = [n for n in target["inbox"] if n["expires_at_ms"] > now]
                require(len(inbox) < MAX_NOTICES, 409, "INBOX_LIMIT")
                inbox.append(
                    {
                        "id": identifier,
                        "sender_uid": actor.uid,
                        "sender": sender["public_id"],
                        "nickname": sender["nickname"],
                        "room_id": room["id"],
                        "slug": slug,
                        "text": command.text,
                        "created_at_ms": now,
                        "expires_at_ms": now + 7 * DAY,
                        "read": False,
                    }
                )
                target["inbox"] = inbox
                save(unit, target)
            pings.append({"room_id": room["id"], "recipients": command.recipients, "at_ms": now})
            sender["pings"] = pings
            save(unit, sender)
            return {"status": "queued", "target_uids": [target["uid"] for target in targets]}, True

        result = self._command(actor, "ping", slug, command, execute)
        targets = result.pop("target_uids", [])
        if result["status"] == "queued":
            self.hub.notify(targets)
        return result

    def read_notice(self, actor, command):
        def execute(unit, now, previous):
            person = self._scope(unit, actor)
            item = next(
                (
                    n
                    for n in person["inbox"]
                    if n["id"] == command.notice_id and n["expires_at_ms"] > now
                ),
                None,
            )
            require(item, 404, "NOTICE_NOT_FOUND")
            if previous or item["read"]:
                return {"ok": True}, False
            item["read"] = True
            save(unit, person)
            return {"ok": True}, True

        return self._command(actor, "notice.read", actor.uid, command, execute)

    def location(self, actor, slug, action, command):
        def read(unit):
            room = self._room(unit, actor, slug)
            if action == "propose":
                require(can(room, actor.uid, "organizer"))
            return True

        self.store.run(read)
        return self.hub.location_command(slug, actor.uid, action, command)


def public_profile(unit, uid):
    value = profile(unit, uid)
    return {**public(value), "privacy": value["privacy"]}
