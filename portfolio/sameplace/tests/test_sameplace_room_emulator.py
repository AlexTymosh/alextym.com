"""Opt-in integration test; never contacts a live Firebase project."""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sameplace.rooms.models import Actor, CreateRoom
from sameplace.rooms.service import RoomError, RoomService
from sameplace.rooms.store import FirestoreStore


@pytest.mark.skipif(
    os.getenv("SAMEPLACE_RUN_EMULATOR") != "1", reason="Opt-in local Firestore Emulator"
)
def test_emulator_serializes_competing_final_room_slots():
    host = os.getenv("FIRESTORE_EMULATOR_HOST", "")
    if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", host) or os.getenv("RENDER"):
        pytest.fail("Only a loopback Firestore Emulator is allowed")
    from google.auth.credentials import AnonymousCredentials
    from google.cloud import firestore

    db = firestore.Client(
        project="demo-sameplace-" + uuid4().hex[:8], credentials=AnonymousCredentials()
    )
    service = RoomService(FirestoreStore(db, firestore.transactional))
    actor = Actor(uid="synthetic-owner", platform_owner=True)

    def create(slug):
        try:
            return service.create(
                actor, CreateRoom(request_id=uuid4().hex, slug=slug, name="Room", capacity=3)
            )["id"]
        except RoomError as error:
            return error.code

    assert create("first") != "OWNER_LIMIT"
    assert create("second") != "OWNER_LIMIT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ["third", "fourth"]))
    assert results.count("OWNER_LIMIT") == 1
    assert len(service.list_rooms(actor)["rooms"]) == 3
