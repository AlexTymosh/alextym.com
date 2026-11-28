"""Scene, template and audio persistence over the real application services."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sameplace.decor.catalog import BACKGROUNDS, SKINS, SURFACES, catalogue, preset
from sameplace.decor.models import DeleteTemplate, MusicCommand, PublishScene, SaveTemplate, Scene
from sameplace.decor.service import DecorService, position
from sameplace.decor.sources import sources
from sameplace.rooms import models as m
from sameplace.rooms.service import RoomError, RoomService
from sameplace.rooms.store import MemoryStore


def cmd(model, **kwargs):
    return model(request_id=uuid4().hex, **kwargs)


@pytest.fixture
def context():
    now = [10000]
    store = MemoryStore()
    core = RoomService(store, lambda: now[0])
    owner = m.Actor(uid="owner", platform_owner=True)
    guest = m.Actor(uid="guest")
    outsider = m.Actor(uid="outsider")
    core.create(owner, cmd(m.CreateRoom, slug="friday", name="Friday", capacity=4))
    invite = core.change(
        owner, "friday", "invite", cmd(m.Invite, version=1, target_kind="uid", target="guest")
    )
    core.redeem(guest, cmd(m.Redeem, token=invite["invitation_token"]))
    return core, DecorService(store, lambda: now[0]), store, owner, guest, outsider, now


def fails(code, callback):
    with pytest.raises(RoomError) as error:
        callback()
    assert error.value.code == code


def test_catalogue_is_bounded_and_every_scene_valid():
    assert len(BACKGROUNDS) == 5 and len(SKINS) == 3
    assert len(catalogue()["scenes"]) == 5
    for background in BACKGROUNDS:
        scene = Scene.model_validate(preset(background))
        assert scene.surface in SURFACES[background]
        assert len(SURFACES[background]) >= 2
    assert preset("beach")["surface"].startswith("mat")
    assert preset("kindergarten_boat")["surface"].startswith("boat")
    assert sum(o["asset_id"] == "speaker_s50" for o in preset("apartment")["objects"]) == 2


@pytest.mark.parametrize(
    "case", ["unknown", "duplicate", "wrong_surface", "bounds", "too_many", "url"]
)
def test_scene_rejects_untrusted_or_invalid_assets(case):
    scene = preset("apartment")
    if case == "unknown":
        scene["objects"][0]["asset_id"] = "unregistered"
    elif case == "duplicate":
        scene["objects"].append(scene["objects"][0])
    elif case == "wrong_surface":
        scene["surface"] = "mat_blue"
    elif case == "bounds":
        scene["objects"][0]["x"] = -1
    elif case == "too_many":
        scene["objects"] *= 20
    else:
        scene["objects"][0]["url"] = "https://example.invalid/asset"
    with pytest.raises(ValidationError):
        Scene.model_validate(scene)


def test_room_membership_read_is_private_and_read_only(context):
    _, decor, store, owner, guest, outsider, _ = context
    old = deepcopy(store.records)
    assert decor.get(owner, "friday")["can_design"]
    assert not decor.get(guest, "friday")["can_dj"]
    fails("ROOM_NOT_FOUND", lambda: decor.get(outsider, "friday"))
    assert old == store.records


def test_scene_conflicts_and_replay(context):
    core, decor, store, owner, guest, _, _ = context
    view = decor.get(owner, "friday")
    command = cmd(
        PublishScene,
        location="lounge",
        revision=0,
        room_version=view["room_version"],
        scene=Scene.model_validate(preset("beach")),
    )
    fails("ACCESS_DENIED", lambda: decor.publish(guest, "friday", command))
    result = decor.publish(owner, "friday", command)
    assert result["scenes"]["lounge"]["revision"] == 1
    assert result["scenes"]["table"]["revision"] == 0
    assert core.get(owner, "friday")["interior"] == "apartment"
    old = deepcopy(store.records)
    assert decor.publish(owner, "friday", command)["scenes"] == result["scenes"]
    assert old == store.records
    fails(
        "SCENE_CONFLICT",
        lambda: decor.publish(
            owner, "friday", command.model_copy(update={"request_id": uuid4().hex})
        ),
    )


def test_template_private_reusable_across_rooms_and_revisioned(context):
    core, decor, _, owner, guest, _, _ = context
    scene = Scene.model_validate(preset("garage"))
    result = decor.template(owner, "friday", cmd(SaveTemplate, name="My garage", scene=scene))
    item = result["templates"][0]
    assert decor.get(guest, "friday")["templates"] == []
    core.create(owner, cmd(m.CreateRoom, slug="second", name="Second", capacity=3))
    assert decor.get(owner, "second")["templates"][0]["id"] == item["id"]
    result = decor.template(
        owner,
        "second",
        cmd(SaveTemplate, name="New", scene=scene, template_id=item["id"], revision=1),
    )
    assert result["templates"][0]["revision"] == 2
    fails(
        "SCENE_CONFLICT",
        lambda: decor.template(
            owner, "friday", cmd(DeleteTemplate, template_id=item["id"], revision=1), delete=True
        ),
    )
    assert (
        decor.template(
            owner, "friday", cmd(DeleteTemplate, template_id=item["id"], revision=2), delete=True
        )["templates"]
        == []
    )


def test_music_permissions_epoch_inheritance_and_skin_independence(context):
    _, decor, _, owner, guest, _, now = context
    play = cmd(MusicCommand, scope="room", revision=0, action="play")
    fails("ACCESS_DENIED", lambda: decor.music(guest, "friday", play))
    view = decor.music(owner, "friday", play)
    track = view["music"]["room"]
    assert track["playback"] == "playing"
    now[0] += 2500
    assert position(track, view["sources"][track["source_id"]], now[0]) == 2500
    scene = preset("card_club")
    scene["skin"] = "mayak_233"
    result = decor.publish(
        owner,
        "friday",
        cmd(
            PublishScene,
            location="lounge",
            revision=0,
            room_version=view["room_version"],
            scene=Scene.model_validate(scene),
        ),
    )
    assert result["music"]["room"] == track
    override = decor.music(
        owner, "friday", cmd(MusicCommand, scope="table", revision=0, action="pause")
    )
    assert override["music"]["table"]["position_ms"] == 2500
    assert override["music"]["room"] == track
    inherited = decor.music(
        owner, "friday", cmd(MusicCommand, scope="table", revision=1, action="inherit")
    )
    assert "table" not in inherited["music"] and inherited["music_versions"]["table"] == 2
    fails(
        "MUSIC_CONFLICT",
        lambda: decor.music(
            owner, "friday", cmd(MusicCommand, scope="table", revision=0, action="play")
        ),
    )


def test_unverified_radio_never_selected(context, monkeypatch):
    _, decor, _, owner, _, _, _ = context
    monkeypatch.setenv("SAMEPLACE_RADIO_DISCO_URL", "https://radio.example.invalid/live")
    monkeypatch.delenv("SAMEPLACE_RADIO_DISCO_RIGHTS_VERIFIED", raising=False)
    assert not sources()["melodia_disco"]["available"]
    fails(
        "SOURCE_UNAVAILABLE",
        lambda: decor.music(
            owner,
            "friday",
            cmd(MusicCommand, scope="room", revision=0, action="select", source_id="melodia_disco"),
        ),
    )
    monkeypatch.setenv("SAMEPLACE_RADIO_DISCO_RIGHTS_VERIFIED", "true")
    assert sources()["melodia_disco"]["available"]
    monkeypatch.setenv(
        "SAMEPLACE_RADIO_DISCO_URL", "https://user:password@radio.example.invalid/live"
    )
    assert not sources()["melodia_disco"]["available"]
