"""Transactional social behavior and privacy under deterministic clocks."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sameplace.rooms import models as r
from sameplace.rooms.service import RoomError, RoomService
from sameplace.rooms.store import MemoryStore
from sameplace.social import models as m
from sameplace.social.hub import Hub
from sameplace.social.service import SocialService, public_id, CHAT_RETENTION


def cmd(model, **values):
    return model(request_id=uuid4().hex, **values)


def error(code, operation):
    with pytest.raises(RoomError) as caught:
        operation()
    assert caught.value.code == code


@pytest.fixture
def context():
    clock = [100.0]
    wall = [100_000]
    store = MemoryStore()
    core = RoomService(store, lambda: wall[0])
    hub = Hub(lambda: clock[0], lambda: wall[0])
    social = SocialService(store, hub, lambda: wall[0])
    owner = r.Actor(uid="owner", platform_owner=True)
    guest = r.Actor(uid="guest")
    third = r.Actor(uid="third")
    stranger = r.Actor(uid="stranger")
    room = core.create(owner, cmd(r.CreateRoom, slug="friday", name="Friday", capacity=2))
    for person in (guest, third):
        invitation = core.change(
            owner,
            "friday",
            "invite",
            cmd(r.Invite, version=room["version"], target_kind="uid", target=person.uid),
        )
        room = core.redeem(person, cmd(r.Redeem, token=invitation["invitation_token"]))
    for person in (owner, guest, third):
        social.set_profile(person, cmd(m.Profile, nickname=person.uid, privacy=m.Privacy()))
    return core, social, hub, owner, guest, third, stranger, clock, wall


def enter(social, hub, person, slug="friday"):
    secret = hub.issue(person.uid, slug, "https://example.invalid", "synthetic")
    ticket = hub.consume(secret, "https://example.invalid")
    epoch = hub.version()
    return hub.admit(ticket, social.access(person, slug), epoch)


def friends(social, left, right):
    social.friend(left, cmd(m.Friend, action="request", target=public_id(right.uid)))
    social.friend(right, cmd(m.Friend, action="accept", target=public_id(left.uid)))


def test_capacity_race_counts_people_not_tabs(context):
    _, social, hub, owner, guest, third, _, _, _ = context
    first = enter(social, hub, owner)
    second = enter(social, hub, owner)
    assert first != second
    error("TAB_LIMIT", lambda: enter(social, hub, owner))

    def attempt(actor):
        try:
            return enter(social, hub, actor)
        except RoomError as e:
            return e.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(attempt, [guest, third]))
    assert values.count("WAIT_CAPACITY") == 1
    assert len(hub.snapshot("friday", owner.uid, first)["people"]) == 2
    hub.leave("friday", owner.uid, first)
    assert hub.in_room("friday", owner.uid)
    hub.leave("friday", owner.uid, second)
    assert not hub.in_room("friday", owner.uid)


def test_global_limit_and_existing_meetings_not_evicted(context):
    core, social, hub, owner, guest, _, _, _, _ = context
    core.create(owner, cmd(r.CreateRoom, slug="second", name="Second", capacity=2))
    core.limits(
        owner,
        cmd(r.Limits, storage_rooms=100, active_rooms=1, active_participants=2, capacity_ceiling=2),
    )
    connection = enter(social, hub, owner, "second")
    error("WAIT_CAPACITY", lambda: enter(social, hub, guest))
    error("OTHER_MEETING", lambda: enter(social, hub, owner))
    assert hub.alive("second", owner.uid, connection)


def test_ticket_origin_single_use_expiry_and_epoch_fence(context):
    _, social, hub, owner, _, _, _, clock, _ = context
    secret = hub.issue(owner.uid, "friday", "https://example.invalid", "secret")
    error("TICKET_INVALID", lambda: hub.consume(secret, "https://evil.invalid"))
    ticket = hub.consume(secret, "https://example.invalid")
    assert "secret" not in repr(ticket)
    error("TICKET_INVALID", lambda: hub.consume(secret, "https://example.invalid"))
    epoch = hub.version()
    hub.fence("friday")
    error("RETRY_REALTIME", lambda: hub.admit(ticket, social.access(owner, "friday"), epoch))
    expired = hub.issue(owner.uid, "friday", "https://example.invalid", "secret")
    clock[0] += 26
    error("TICKET_INVALID", lambda: hub.consume(expired, "https://example.invalid"))


def test_meeting_grace_expiry_and_restart(context):
    _, social, hub, owner, _, _, _, clock, _ = context
    one = enter(social, hub, owner)
    first = hub.snapshot("friday", owner.uid, one)["meeting_id"]
    hub.leave("friday", owner.uid, one)
    clock[0] += 20
    two = enter(social, hub, owner)
    assert hub.snapshot("friday", owner.uid, two)["meeting_id"] == first
    hub.leave("friday", owner.uid, two)
    clock[0] += 91
    three = enter(social, hub, owner)
    assert hub.snapshot("friday", owner.uid, three)["meeting_id"] != first
    clock[0] += 91
    assert not hub.alive("friday", owner.uid, three)
    assert Hub().meetings == {}


def test_hub_ping_does_not_touch_store(context):
    _, social, hub, owner, _, _, _, clock, _ = context
    connection = enter(social, hub, owner)
    before = dict(social.store.records)
    for _ in range(20):
        clock[0] += 20
        assert hub.ping("friday", owner.uid, connection)
        hub.snapshot("friday", owner.uid, connection)
    assert social.store.records == before


def test_friend_privacy_bilateral_and_room_membership(context):
    core, social, hub, owner, guest, third, stranger, _, _ = context
    error("ACCESS_DENIED", lambda: social.me(stranger))
    friends(social, owner, guest)
    connection = enter(social, hub, guest)
    item = social.me(owner)["friends"][0]
    assert item["presence"] == "online" and "room" not in item and "uid" not in item
    social.set_profile(
        guest,
        cmd(
            m.Profile,
            nickname="Guest",
            privacy=m.Privacy(show_online=False, show_room=True, show_last_seen=True),
        ),
    )
    item = social.me(owner)["friends"][0]
    assert item["presence"] == "hidden" and "room" not in item and "last_seen_ms" not in item
    assert hub.snapshot("friday", guest.uid, connection)["people"][0]["nickname"] == "Guest"
    assert social.me(third)["friends"] == []
    social.friend(owner, cmd(m.Friend, action="remove", target=public_id(guest.uid)))
    assert core.get(guest, "friday")["slug"] == "friday"


def test_room_status_not_disclosed_without_shared_membership(context):
    core, social, hub, owner, guest, third, _, _, _ = context
    friends(social, guest, third)
    private = core.create(owner, cmd(r.CreateRoom, slug="private", name="Private", capacity=2))
    token = core.change(
        owner,
        "private",
        "invite",
        cmd(r.Invite, version=private["version"], target_kind="uid", target=guest.uid),
    )
    core.redeem(guest, cmd(r.Redeem, token=token["invitation_token"]))
    social.set_profile(guest, cmd(m.Profile, nickname="Guest", privacy=m.Privacy(show_room=True)))
    enter(social, hub, guest, "private")
    item = social.me(third)["friends"][0]
    assert item["presence"] == "online" and "room" not in item
    assert social.me(owner)["friends"] == []


def test_friend_block_does_not_revoke_room_and_prevents_ping(context):
    core, social, hub, owner, guest, _, _, _, _ = context
    friends(social, owner, guest)
    social.friend(guest, cmd(m.Friend, action="block", target=public_id(owner.uid)))
    enter(social, hub, owner)
    assert social.recipients(owner, "friday")["recipients"] == [
        {"public_id": public_id("third"), "nickname": "third", "avatar": "initials", "channels": []}
    ]
    assert core.get(owner, "friday")["slug"] == "friday"
    error(
        "NOTIFICATION_CONSENT",
        lambda: social.ping(
            owner,
            "friday",
            cmd(m.Ping, recipients=[public_id(guest.uid)], channel="internal", text="hello"),
        ),
    )


def test_chat_expiry_plain_text_idempotency_and_moderation(context):
    _, social, hub, owner, guest, third, stranger, _, wall = context
    enter(social, hub, guest)
    request = cmd(m.ChatSend, text="<script>alert(1)</script>")
    result = social.send(guest, "friday", request)
    assert social.send(guest, "friday", request) == result
    assert social.chat(owner, "friday")["messages"][0]["text"] == request.text
    error(
        "REQUEST_CONFLICT",
        lambda: social.send(guest, "friday", request.model_copy(update={"text": "different"})),
    )
    error("ROOM_NOT_FOUND", lambda: social.chat(stranger, "friday"))
    error(
        "ACCESS_DENIED",
        lambda: social.hide(
            third, "friday", cmd(m.ChatHide, message_id=result["id"], reason="reason")
        ),
    )
    error(
        "ACCESS_DENIED",
        lambda: social.hide(owner, "friday", cmd(m.ChatHide, message_id=result["id"])),
    )
    social.hide(owner, "friday", cmd(m.ChatHide, message_id=result["id"], reason="moderation"))
    assert social.chat(guest, "friday")["messages"] == []
    social.send(guest, "friday", cmd(m.ChatSend, text="another"))
    wall[0] += CHAT_RETENTION
    assert social.chat(owner, "friday")["messages"] == []
    assert social.cleanup_chat(owner, "friday")["removed"] == 2


def test_chat_cursor_paging_and_rate_limit(context):
    _, social, hub, owner, guest, _, _, _, wall = context
    enter(social, hub, guest)
    for n in range(55):
        wall[0] += 60001
        social.send(guest, "friday", cmd(m.ChatSend, text=str(n)))
    latest = social.chat(owner, "friday")
    assert len(latest["messages"]) == 50 and latest["before"]
    older = social.chat(owner, "friday", latest["before"])
    assert [m["text"] for m in older["messages"]] == [str(n) for n in range(5)]
    assert older["before"] is None
    wall[0] += 60001
    for _ in range(12):
        social.send(guest, "friday", cmd(m.ChatSend, text="rate"))
    error("RATE_LIMIT", lambda: social.send(guest, "friday", cmd(m.ChatSend, text="rate")))


def test_notification_consent_stub_dedupe_and_scope(context):
    _, social, hub, owner, guest, third, stranger, _, _ = context
    enter(social, hub, owner)
    friends(social, owner, guest)
    error(
        "ACCESS_DENIED",
        lambda: social.ping(
            owner,
            "friday",
            cmd(m.Ping, recipients=[public_id(stranger.uid)], channel="internal", text="wait"),
        ),
    )
    error(
        "NOTIFICATION_CONSENT",
        lambda: social.ping(
            owner,
            "friday",
            cmd(m.Ping, recipients=[public_id(third.uid)], channel="internal", text="wait"),
        ),
    )
    social.set_profile(
        guest,
        cmd(
            m.Profile,
            nickname="Guest",
            privacy=m.Privacy(allow_email_pings=True, allow_sms_pings=True),
        ),
    )
    before = dict(social.store.records)
    for channel in ("email", "sms"):
        assert social.ping(
            owner,
            "friday",
            cmd(m.Ping, recipients=[public_id(guest.uid)], channel=channel, text="wait"),
        ) == {"status": "disabled"}
    assert social.store.records == before
    request = cmd(m.Ping, recipients=[public_id(guest.uid)], channel="internal", text="wait")
    assert social.ping(owner, "friday", request) == {"status": "queued"}
    assert social.ping(owner, "friday", request) == {"status": "queued"}
    notices = social.me(guest)["notices"]
    assert len(notices) == 1 and "sender_uid" not in notices[0] and notices[0]["slug"] == "friday"
    error(
        "RATE_LIMIT",
        lambda: social.ping(
            owner,
            "friday",
            cmd(m.Ping, recipients=[public_id(guest.uid)], channel="internal", text="again"),
        ),
    )
    social.read_notice(guest, cmd(m.NoticeRead, notice_id=notices[0]["id"]))
    assert social.me(guest)["notices"][0]["read"]


def test_location_accept_decline_and_no_seat(context):
    _, social, hub, owner, guest, _, _, _, _ = context
    one = enter(social, hub, owner)
    two = enter(social, hub, guest)
    proposal = social.location(
        owner,
        "friday",
        "propose",
        cmd(m.Proposal, location="table", role="play", recipients=[public_id(guest.uid)]),
    )
    social.location(
        guest, "friday", "answer", cmd(m.ProposalAnswer, proposal_id=proposal["id"], accept=False)
    )
    snap = hub.snapshot("friday", guest.uid, two)
    assert next(p for p in snap["people"] if p["self"])["location"] == "lounge"
    assert snap["proposals"][0]["responses"][public_id(guest.uid)] == "declined"
    proposal = social.location(
        owner,
        "friday",
        "propose",
        cmd(m.Proposal, location="table", role="play", recipients=[public_id(guest.uid)]),
    )
    social.location(
        guest, "friday", "answer", cmd(m.ProposalAnswer, proposal_id=proposal["id"], accept=True)
    )
    person = next(p for p in hub.snapshot("friday", owner.uid, one)["people"] if not p["self"])
    assert person["location"] == "table" and person["role"] == "visit" and "seat" not in person


def test_favourites_and_recent_are_room_scoped(context):
    _, social, hub, owner, guest, _, stranger, _, _ = context
    enter(social, hub, owner)
    social.visit(owner, "friday")
    before = dict(social.store.records)
    social.visit(owner, "friday")
    assert before == social.store.records
    social.favourite(guest, "friday", cmd(m.Favourite, enabled=True))
    assert social.me(guest)["favourites"]
    error(
        "ROOM_NOT_FOUND",
        lambda: social.favourite(stranger, "friday", cmd(m.Favourite, enabled=True)),
    )
