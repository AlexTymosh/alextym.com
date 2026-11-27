"""Bounded single-process meeting hub. No provider, network or database access.

All methods synchronize on one lock. A ticket is consumed once, then fresh
identity and room authorization must precede admission. A process restart
loses presence only, never durable room, chat or game data.
"""

from dataclasses import dataclass, field
from threading import RLock
from time import monotonic, time
from uuid import uuid4
from secrets import token_urlsafe
from copy import deepcopy
from ..rooms.service import require

TICKET_SECONDS = 25
LEASE_SECONDS = 90
GRACE_SECONDS = 90
AUTH_SECONDS = 60
MAX_TICKETS = 128
MAX_CONNECTIONS = 120
MAX_TABS = 2
MAX_PROPOSALS = 8


@dataclass(repr=False)
class Ticket:
    uid: str
    slug: str
    origin: str
    authorization: str
    expires: float


@dataclass
class Person:
    public_id: str
    nickname: str
    avatar: str
    location: str = "lounge"
    role: str = "visit"
    connections: dict[str, float] = field(default_factory=dict)
    commands: dict[str, tuple[str, dict]] = field(default_factory=dict)


@dataclass
class Meeting:
    room_id: str
    id: str = field(default_factory=lambda: uuid4().hex)
    people: dict[str, Person] = field(default_factory=dict)
    proposals: dict[str, dict] = field(default_factory=dict)
    idle_at: float | None = None
    sequence: int = 0
    chat_revision: int = 0
    room_revision: int = 0


class Hub:
    def __init__(self, clock=monotonic, wall=lambda: int(time() * 1000)):
        self.clock = clock
        self.wall = wall
        self.lock = RLock()
        self.tickets: dict[str, Ticket] = {}
        self.meetings: dict[str, Meeting] = {}
        self.epoch = 0
        self.inbox_revision: dict[str, int] = {}
        self.last_seen: dict[str, int] = {}
        self.public_last_seen: set[str] = set()
        self.handshakes = 0

    def _touch(self, meeting):
        meeting.sequence += 1

    def _cleanup(self):
        now = self.clock()
        for key in list(self.tickets):
            if self.tickets[key].expires <= now:
                del self.tickets[key]
        for slug, meeting in list(self.meetings.items()):
            for uid, person in list(meeting.people.items()):
                for connection, expiry in list(person.connections.items()):
                    if expiry <= now:
                        del person.connections[connection]
                if not person.connections:
                    self._remove(meeting, uid)
            for proposal in meeting.proposals.values():
                if proposal["deadline"] <= now:
                    for target, status in proposal["responses"].items():
                        if status == "pending":
                            proposal["responses"][target] = "expired"
                            self._touch(meeting)
            if (
                not meeting.people
                and meeting.idle_at is not None
                and now - meeting.idle_at >= GRACE_SECONDS
            ):
                del self.meetings[slug]

    def _remove(self, meeting, uid):
        person = meeting.people.pop(uid)
        for proposal in meeting.proposals.values():
            if proposal["sender"] == person.public_id:
                for target, status in proposal["responses"].items():
                    if status == "pending":
                        proposal["responses"][target] = "cancelled"
            elif proposal["responses"].get(person.public_id) == "pending":
                proposal["responses"][person.public_id] = "expired"
        if uid in self.public_last_seen:
            self.last_seen[uid] = self.wall()
            self.public_last_seen.discard(uid)
            if len(self.last_seen) > 512:
                self.last_seen.pop(next(iter(self.last_seen)))
        self._touch(meeting)
        if not meeting.people:
            meeting.idle_at = self.clock()

    def begin_handshake(self):
        with self.lock:
            if self.handshakes >= 32:
                return False
            self.handshakes += 1
            return True

    def end_handshake(self):
        with self.lock:
            self.handshakes -= 1

    def version(self):
        with self.lock:
            return self.epoch

    def issue(self, uid, slug, origin, authorization):
        with self.lock:
            self._cleanup()
            require(len(self.tickets) < MAX_TICKETS, 429, "REALTIME_BUSY")
            require(sum(t.uid == uid for t in self.tickets.values()) < 4, 429, "REALTIME_BUSY")
            token = token_urlsafe(32)
            self.tickets[token] = Ticket(
                uid, slug, origin, authorization, self.clock() + TICKET_SECONDS
            )
            return token

    def consume(self, token, origin):
        with self.lock:
            self._cleanup()
            ticket = self.tickets.get(token)
            require(ticket is not None and ticket.origin == origin, 403, "TICKET_INVALID")
            del self.tickets[token]
            return ticket

    def admit(self, ticket, access, epoch):
        with self.lock:
            self._cleanup()
            require(epoch == self.epoch, 409, "RETRY_REALTIME")
            slug, uid = ticket.slug, ticket.uid
            room, limits, profile = access["room"], access["limits"], access["profile"]
            require(room["slug"] == slug and room["status"] == "active", 404, "ROOM_NOT_FOUND")
            require(
                not any(uid in m.people for key, m in self.meetings.items() if key != slug),
                409,
                "OTHER_MEETING",
            )
            meeting = self.meetings.get(slug)
            existing = meeting.people.get(uid) if meeting else None
            active = [m for m in self.meetings.values() if m.people]
            require(
                sum(len(p.connections) for m in active for p in m.people.values())
                < MAX_CONNECTIONS,
                429,
                "REALTIME_BUSY",
            )
            if existing:
                require(len(existing.connections) < MAX_TABS, 409, "TAB_LIMIT")
            else:
                require(
                    not (meeting is None or not meeting.people)
                    or len(active) < limits["active_rooms"],
                    409,
                    "WAIT_CAPACITY",
                )
                require(
                    sum(len(m.people) for m in active) < limits["active_participants"],
                    409,
                    "WAIT_CAPACITY",
                )
                require(
                    (len(meeting.people) if meeting else 0)
                    < min(room["capacity"], limits["capacity_ceiling"]),
                    409,
                    "WAIT_CAPACITY",
                )
                # Bound grace entries even if many distinct rooms are visited rapidly.
                if meeting is None:
                    require(len(self.meetings) < 100, 429, "REALTIME_BUSY")
                    meeting = self.meetings[slug] = Meeting(room["id"])
                person = Person(profile["public_id"], profile["nickname"], profile["avatar"])
                meeting.people[uid] = person
                if profile["privacy"]["show_online"] and profile["privacy"]["show_last_seen"]:
                    self.public_last_seen.add(uid)
                self._touch(meeting)
            person = meeting.people[uid]
            connection = uuid4().hex
            person.connections[connection] = self.clock() + LEASE_SECONDS
            meeting.idle_at = None
            return connection

    def fence(self, slug=None):
        with self.lock:
            self.epoch += 1
            if slug in self.meetings:
                self.meetings[slug].room_revision += 1
                self._touch(self.meetings[slug])

    def invalidate(self, slug=None, uid=None):
        """Core changes fence concurrent admission and invalidate affected leases."""
        with self.lock:
            self.epoch += 1
            for key, ticket in list(self.tickets.items()):
                if (slug is None or ticket.slug == slug) and (uid is None or ticket.uid == uid):
                    del self.tickets[key]
            for key, meeting in self.meetings.items():
                if slug is None or key == slug:
                    meeting.room_revision += 1
                    self._touch(meeting)
                    for user in list(meeting.people):
                        if uid is None or user == uid:
                            self._remove(meeting, user)

    def leave(self, slug, uid, connection):
        with self.lock:
            meeting = self.meetings.get(slug)
            person = meeting.people.get(uid) if meeting else None
            if person and connection in person.connections:
                del person.connections[connection]
                if not person.connections:
                    self._remove(meeting, uid)

    def alive(self, slug, uid, connection):
        with self.lock:
            self._cleanup()
            meeting = self.meetings.get(slug)
            return bool(
                meeting and uid in meeting.people and connection in meeting.people[uid].connections
            )

    def ping(self, slug, uid, connection):
        with self.lock:
            if not self.alive(slug, uid, connection):
                return False
            self.meetings[slug].people[uid].connections[connection] = self.clock() + LEASE_SECONDS
            return True

    def in_room(self, slug, uid):
        with self.lock:
            self._cleanup()
            meeting = self.meetings.get(slug)
            return bool(meeting and uid in meeting.people)

    def profile_changed(self, uid, profile):
        with self.lock:
            # Never retain a timestamp of a formerly hidden visit when privacy is re-enabled.
            self.last_seen.pop(uid, None)
            self.public_last_seen.discard(uid)
            for meeting in self.meetings.values():
                if uid in meeting.people:
                    person = meeting.people[uid]
                    person.nickname, person.avatar = profile["nickname"], profile["avatar"]
                    self._touch(meeting)

    def presence(self, uid):
        with self.lock:
            self._cleanup()
            for slug, meeting in self.meetings.items():
                if uid in meeting.people:
                    return slug, None
            return None, self.last_seen.get(uid)

    def chat_changed(self, slug):
        with self.lock:
            if slug in self.meetings:
                meeting = self.meetings[slug]
                meeting.chat_revision += 1
                self._touch(meeting)

    def notify(self, uids):
        with self.lock:
            for uid in uids:
                self.inbox_revision[uid] = self.inbox_revision.get(uid, 0) + 1
            while len(self.inbox_revision) > 512:
                self.inbox_revision.pop(next(iter(self.inbox_revision)))

    def snapshot(self, slug, uid, connection):
        with self.lock:
            require(self.alive(slug, uid, connection), 403, "REALTIME_REVOKED")
            meeting = self.meetings[slug]
            return {
                "protocol_version": 1,
                "type": "room.snapshot",
                "room_id": meeting.room_id,
                "meeting_id": meeting.id,
                "sequence": meeting.sequence,
                "chat_revision": meeting.chat_revision,
                "room_revision": meeting.room_revision,
                "inbox_revision": self.inbox_revision.get(uid, 0),
                "server_now_ms": self.wall(),
                "people": [
                    {
                        "id": p.public_id,
                        "nickname": p.nickname,
                        "avatar": p.avatar,
                        "location": p.location,
                        "role": p.role,
                        "self": key == uid,
                    }
                    for key, p in meeting.people.items()
                ],
                "proposals": [
                    {k: deepcopy(v) for k, v in p.items() if k not in {"deadline", "request_id"}}
                    for p in meeting.proposals.values()
                ],
            }

    def _meeting(self, slug, uid):
        self._cleanup()
        require(self.in_room(slug, uid), 409, "JOIN_MEETING_REQUIRED")
        return self.meetings[slug]

    def location_command(self, slug, uid, action, command):
        with self.lock:
            meeting = self._meeting(slug, uid)
            person = meeting.people[uid]
            fingerprint = action + "\0" + command.model_dump_json()
            receipt = person.commands.get(command.request_id)
            if receipt:
                require(receipt[0] == fingerprint, 409, "REQUEST_CONFLICT")
                return deepcopy(receipt[1])
            handler = {
                "propose": self.propose,
                "answer": self.answer,
                "cancel": self.cancel,
                "move": self.move,
            }[action]
            result = handler(slug, uid, command)
            person.commands[command.request_id] = (fingerprint, deepcopy(result))
            if len(person.commands) > 64:
                person.commands.pop(next(iter(person.commands)))
            return result

    def propose(self, slug, uid, command):
        with self.lock:
            meeting = self._meeting(slug, uid)
            sender = meeting.people[uid].public_id
            for proposal in meeting.proposals.values():
                if proposal["sender"] == sender and proposal["request_id"] == command.request_id:
                    require(
                        proposal["location"] == command.location
                        and proposal["role"] == command.role
                        and set(proposal["responses"]) == set(command.recipients),
                        409,
                        "REQUEST_CONFLICT",
                    )
                    return {"id": proposal["id"]}
            known = {p.public_id for key, p in meeting.people.items() if key != uid}
            require(set(command.recipients) <= known, 409, "INVALID_MEMBER")
            for key in list(meeting.proposals):
                if all(s != "pending" for s in meeting.proposals[key]["responses"].values()):
                    del meeting.proposals[key]
            require(len(meeting.proposals) < MAX_PROPOSALS, 409, "PROPOSAL_LIMIT")
            identifier = uuid4().hex
            meeting.proposals[identifier] = {
                "id": identifier,
                "sender": sender,
                "location": command.location,
                "role": command.role,
                "request_id": command.request_id,
                "deadline": self.clock() + 120,
                "expires_at_ms": self.wall() + 120000,
                "responses": {p: "pending" for p in command.recipients},
            }
            self._touch(meeting)
            return {"id": identifier}

    def answer(self, slug, uid, command):
        with self.lock:
            meeting = self._meeting(slug, uid)
            person = meeting.people[uid]
            proposal = meeting.proposals.get(command.proposal_id)
            require(proposal and person.public_id in proposal["responses"], 404, "PROPOSAL_INVALID")
            answer = "accepted" if command.accept else "declined"
            previous = proposal["responses"][person.public_id]
            require(previous in {"pending", answer}, 409, "PROPOSAL_INVALID")
            if previous == "pending":
                proposal["responses"][person.public_id] = answer
                if command.accept:
                    person.location = proposal["location"]
                    # This is a visit preference, not an allocated game seat.
                    person.role = "watch" if proposal["role"] == "watch" else "visit"
                self._touch(meeting)
            return {"status": answer}

    def cancel(self, slug, uid, command):
        with self.lock:
            meeting = self._meeting(slug, uid)
            proposal = meeting.proposals.get(command.proposal_id)
            require(
                proposal and proposal["sender"] == meeting.people[uid].public_id,
                404,
                "PROPOSAL_INVALID",
            )
            for key, value in proposal["responses"].items():
                if value == "pending":
                    proposal["responses"][key] = "cancelled"
            self._touch(meeting)
            return {"ok": True}

    def move(self, slug, uid, command):
        with self.lock:
            meeting = self._meeting(slug, uid)
            person = meeting.people[uid]
            if person.location != command.location:
                person.location, person.role = command.location, "visit"
                self._touch(meeting)
            return {"ok": True}
