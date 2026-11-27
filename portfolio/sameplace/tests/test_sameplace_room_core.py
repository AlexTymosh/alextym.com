from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sameplace.rooms import models as m
from sameplace.rooms.service import RoomError, RoomService, hash_value, user_key
from sameplace.rooms.store import MemoryStore


def cmd(model, **kwargs):
    return model(request_id=uuid4().hex, **kwargs)


@pytest.fixture
def context():
    store = MemoryStore()
    now = [100_000]
    service = RoomService(store, lambda: now[0])
    owner = m.Actor(uid="owner", platform_owner=True)
    guest = m.Actor(uid="guest", verified_email="guest@example.invalid")
    stranger = m.Actor(uid="stranger", verified_email="other@example.invalid")
    return service, store, now, owner, guest, stranger


def create(service, actor, slug="friday", **kwargs):
    return service.create(actor, cmd(m.CreateRoom, slug=slug, name="Room", capacity=3, **kwargs))


def change(service, actor, room, action, model=m.Versioned, **kwargs):
    return service.change(
        actor, room["slug"], action, cmd(model, version=room["version"], **kwargs)
    )


def invite(service, owner, room, guest, **kwargs):
    return change(
        service, owner, room, "invite", m.Invite, target_kind="uid", target=guest.uid, **kwargs
    )


def redeem(service, guest, invitation):
    return service.redeem(guest, cmd(m.Redeem, token=invitation["invitation_token"]))


def assert_error(code, callback):
    with pytest.raises(RoomError) as error:
        callback()
    assert error.value.code == code


def test_no_creator_permission_without_owner_approval(context):
    s, store, _, owner, guest, _ = context
    assert_error("ACCESS_DENIED", lambda: create(s, guest))
    assert store.records == {}
    s.approve(owner, cmd(m.Approval, uid=guest.uid, approved=True))
    assert create(s, guest)["is_owner"]
    s.approve(owner, cmd(m.Approval, uid=guest.uid, approved=False))
    assert_error("ACCESS_DENIED", lambda: create(s, guest, "next-room"))


def test_concurrent_fourth_room_is_rejected(context):
    s, _, _, owner, _, _ = context

    def attempt(n):
        try:
            return create(s, owner, f"room-{n}")["id"]
        except RoomError as e:
            return e.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count("OWNER_LIMIT") == 5
    assert len(s.list_rooms(owner)["rooms"]) == 3


def test_slug_conflict_and_create_retry(context):
    s, _, _, owner, guest, _ = context
    request = cmd(m.CreateRoom, slug="friday", name="Room", capacity=3)
    first = s.create(owner, request)
    assert s.create(owner, request)["id"] == first["id"]
    assert_error(
        "REQUEST_CONFLICT", lambda: s.create(owner, request.model_copy(update={"name": "Changed"}))
    )
    s.approve(owner, cmd(m.Approval, uid=guest.uid, approved=True))
    assert_error("SLUG_TAKEN", lambda: create(s, guest))


def test_rename_preserves_slug_and_nonmember_has_no_metadata(context):
    s, _, _, owner, guest, _ = context
    room = create(s, owner)
    assert_error("ROOM_NOT_FOUND", lambda: s.get(guest, room["slug"]))
    assert s.list_rooms(guest)["rooms"] == []
    updated = change(
        s, owner, room, "update", m.UpdateRoom, name="Other", capacity=4, interior="garage"
    )
    assert updated["id"] == room["id"] and updated["slug"] == room["slug"]
    assert s.get(owner, room["slug"])["name"] == "Other"


def test_invite_room_only_and_owner_absent(context):
    s, store, _, owner, guest, stranger = context
    room = create(s, owner)
    other = create(s, owner, "other-room")
    invitation = invite(s, owner, room, guest)
    raw = invitation["invitation_token"]
    assert raw not in repr(store.records)
    assert hash_value(raw) in repr(store.records)
    assert_error("INVITE_INVALID", lambda: redeem(s, stranger, invitation))
    result = redeem(s, guest, invitation)
    assert result["id"] == room["id"] and not result["is_owner"] and result["roles"] == []
    assert "members" not in result and "invites" not in result
    assert s.get(guest, "friday")["id"] == room["id"]
    assert_error("ROOM_NOT_FOUND", lambda: s.get(guest, other["slug"]))
    assert not s.identity(guest)["can_create"]
    assert_error("ACCESS_DENIED", lambda: create(s, guest, "new-room"))
    assert set(record for record in store.records if record.startswith("user_")) == {
        user_key(owner.uid),
        user_key(guest.uid),
    }


def test_email_invite_requires_verified_address(context):
    s, _, _, owner, guest, _ = context
    invitation = change(
        s,
        owner,
        create(s, owner),
        "invite",
        m.Invite,
        target_kind="email",
        target="Guest@EXAMPLE.invalid",
    )
    unverified = m.Actor(uid=guest.uid)
    assert_error("INVITE_INVALID", lambda: redeem(s, unverified, invitation))
    assert redeem(s, guest, invitation)["slug"] == "friday"


def test_invite_replay_same_key_is_safe_new_key_is_denied(context):
    s, _, _, owner, guest, _ = context
    invitation = invite(s, owner, create(s, owner), guest)
    request = cmd(m.Redeem, token=invitation["invitation_token"])
    result = s.redeem(guest, request)
    assert s.redeem(guest, request)["version"] == result["version"]
    assert_error("INVITE_INVALID", lambda: redeem(s, guest, invitation))


def test_expired_and_revoked_invites(context):
    s, _, now, owner, guest, _ = context
    room = invite(s, owner, create(s, owner), guest, days=1)
    now[0] += 86400001
    assert_error("INVITE_INVALID", lambda: redeem(s, guest, room))
    newer = invite(s, owner, s.get(owner, "friday"), guest)
    revoked = change(
        s, owner, newer, "revoke_invite", m.RevokeInvite, invite_id=newer["invites"][0]["id"]
    )
    assert revoked["invites"][0]["status"] == "revoked"
    assert_error("INVITE_INVALID", lambda: redeem(s, guest, newer))


def test_delegation_and_inviter_revocation(context):
    s, _, _, owner, guest, stranger = context
    redeem(s, guest, invite(s, owner, create(s, owner), guest))
    room = s.get(owner, "friday")
    assert_error("ACCESS_DENIED", lambda: invite(s, guest, room, stranger))
    room = change(s, owner, room, "roles", m.SetRoles, uid=guest.uid, roles=["inviter", "designer"])
    guest_view = s.get(guest, "friday")
    assert guest_view["can_invite"]
    changed = change(s, guest, guest_view, "design", m.DesignRoom, interior="beach")
    assert changed["interior"] == "beach"
    invitation = invite(s, guest, changed, stranger)
    changed = change(s, owner, s.get(owner, "friday"), "roles", m.SetRoles, uid=guest.uid, roles=[])
    change(s, owner, changed, "roles", m.SetRoles, uid=guest.uid, roles=["inviter"])
    assert_error("INVITE_INVALID", lambda: redeem(s, stranger, invitation))


def test_block_remove_and_revoke_existing_link(context):
    s, _, now, owner, guest, _ = context
    redeem(s, guest, invite(s, owner, create(s, owner), guest))
    invitation = invite(s, owner, s.get(owner, "friday"), guest)
    now[0] += 1
    blocked = change(s, owner, s.get(owner, "friday"), "block", m.MemberCommand, uid=guest.uid)
    assert_error("ROOM_NOT_FOUND", lambda: s.get(guest, "friday"))
    assert s.list_rooms(guest)["rooms"] == []
    assert_error("INVITE_INVALID", lambda: redeem(s, guest, invitation))
    now[0] += 1
    change(s, owner, blocked, "unblock", m.MemberCommand, uid=guest.uid)
    assert_error("INVITE_INVALID", lambda: redeem(s, guest, invitation))
    now[0] += 1
    assert redeem(s, guest, invite(s, owner, s.get(owner, "friday"), guest))["slug"] == "friday"


def test_archive_frees_slot_reserves_slug_and_restore_checks_limit(context):
    s, _, _, owner, guest, _ = context
    room = create(s, owner)
    redeem(s, guest, invite(s, owner, room, guest))
    create(s, owner, "second")
    create(s, owner, "third")
    archived = change(s, owner, s.get(owner, "friday"), "archive")
    assert archived["status"] == "archived"
    assert_error("ROOM_NOT_FOUND", lambda: s.get(guest, "friday"))
    create(s, owner, "fourth")
    assert_error("OWNER_LIMIT", lambda: change(s, owner, archived, "restore"))
    change(s, owner, s.get(owner, "fourth"), "archive")
    assert change(s, owner, archived, "restore")["id"] == room["id"]
    assert s.get(guest, "friday")["id"] == room["id"]


def test_transfer_requires_two_parties_approval_and_atomic_owner_counts(context):
    s, store, _, owner, guest, stranger = context
    room = create(s, owner)
    redeem(s, guest, invite(s, owner, room, guest))
    room = s.get(owner, "friday")
    assert_error(
        "CREATOR_REQUIRED",
        lambda: change(s, owner, room, "propose_transfer", m.MemberCommand, uid=guest.uid),
    )
    s.approve(owner, cmd(m.Approval, uid=guest.uid, approved=True))
    proposed = change(s, owner, room, "propose_transfer", m.MemberCommand, uid=guest.uid)
    transfer_id = proposed["transfer"]["id"]
    assert_error(
        "ROOM_NOT_FOUND",
        lambda: change(
            s, stranger, proposed, "accept_transfer", m.TransferAccept, transfer_id=transfer_id
        ),
    )
    assert_error(
        "ACCESS_DENIED",
        lambda: change(
            s, owner, proposed, "accept_transfer", m.TransferAccept, transfer_id=transfer_id
        ),
    )
    accepted = change(
        s, guest, proposed, "accept_transfer", m.TransferAccept, transfer_id=transfer_id
    )
    assert accepted["is_owner"] and len([m for m in accepted["members"] if m["owner"]]) == 1
    assert store.records[user_key(owner.uid)]["owned"] == []
    assert store.records[user_key(guest.uid)]["owned"] == [room["id"]]
    assert not s.get(owner, "friday")["is_owner"]


def test_stale_version_cannot_overwrite_room(context):
    s, _, _, owner, guest, _ = context
    room = create(s, owner)
    invite(s, owner, room, guest)
    assert_error("STALE_VERSION", lambda: change(s, owner, room, "archive"))


def test_platform_limits_are_owner_only_and_archive_not_storage_bypass(context):
    s, _, _, owner, guest, _ = context
    limits = cmd(
        m.Limits, storage_rooms=1, active_rooms=1, active_participants=3, capacity_ceiling=3
    )
    assert_error("ACCESS_DENIED", lambda: s.limits(guest, limits))
    s.limits(owner, limits)
    room = create(s, owner)
    change(s, owner, room, "archive")
    assert_error("STORAGE_LIMIT", lambda: create(s, owner, "another"))


@pytest.mark.parametrize("bad", ["a", "-abc", "abc-", "Abc", "../abc", "rooms"])
def test_slug_validation(bad):
    with pytest.raises(ValidationError):
        cmd(m.CreateRoom, slug=bad, name="Room", capacity=3)
