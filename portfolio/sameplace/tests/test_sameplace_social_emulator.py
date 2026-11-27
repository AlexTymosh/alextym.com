"""Opt-in local Emulator integration; never connects to a live provider."""

import os
import re
from uuid import uuid4
import pytest
from sameplace.rooms.models import Actor, CreateRoom
from sameplace.rooms.service import RoomService
from sameplace.rooms.store import FirestoreStore
from sameplace.social.hub import Hub
from sameplace.social.models import ChatSend, Profile, Privacy
from sameplace.social.service import SocialService


@pytest.mark.skipif(
    os.getenv("SAMEPLACE_RUN_EMULATOR") != "1", reason="Opt-in local Firestore Emulator"
)
def test_emulator_social_profile_chat_and_retry():
    host = os.getenv("FIRESTORE_EMULATOR_HOST", "")
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", host) or os.getenv("RENDER"):
        pytest.fail("Only a loopback Firestore Emulator is allowed")
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore

    db = firestore.Client(
        project="demo-sameplace-" + uuid4().hex[:8], credentials=AnonymousCredentials()
    )
    store = FirestoreStore(db, firestore.transactional)
    core = RoomService(store)
    hub = Hub()
    social = SocialService(store, hub)
    owner = Actor(uid="synthetic-owner", platform_owner=True)
    core.create(owner, CreateRoom(request_id=uuid4().hex, slug="friday", name="Room", capacity=2))
    social.set_profile(
        owner, Profile(request_id=uuid4().hex, nickname="Synthetic", privacy=Privacy())
    )
    token = hub.issue(owner.uid, "friday", "https://example.invalid", "synthetic")
    connection = hub.admit(
        hub.consume(token, "https://example.invalid"), social.access(owner, "friday"), hub.version()
    )
    social.visit(owner, "friday")
    request = ChatSend(request_id=uuid4().hex, text="synthetic message")
    assert social.send(owner, "friday", request) == social.send(owner, "friday", request)
    assert len(social.chat(owner, "friday")["messages"]) == 1
    assert social.me(owner)["nickname"] == "Synthetic"
    hub.leave("friday", owner.uid, connection)
