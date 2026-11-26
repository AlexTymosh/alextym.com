from types import SimpleNamespace

from preferans.online.table_experience import mark_activity, settlement_options


def game(**kwargs):
    fields = dict(
        phase=SimpleNamespace(value="play"),
        turn=0,
        declarer=0,
        auction=SimpleNamespace(history=[]),
        completed_tricks=[],
        trick=[],
        defense=[None, None, None],
        mode=None,
        is_passout=False,
        contract=SimpleNamespace(level=6),
        end_reason=SimpleNamespace(value="played"),
        tricks_won=[6, 3, 1],
    )
    fields.update(kwargs)
    return SimpleNamespace(**fields)


def test_activity_timestamp_only_changes_with_game_action():
    room = {"status": "playing", "game_id": "deal"}
    state = game()
    mark_activity(room, state, 100)
    mark_activity(room, state, 500)
    assert room["activity_started_at_ms"] == 100
    state.turn = 1
    mark_activity(room, state, 600)
    assert room["activity_started_at_ms"] == 600
    room["status"] = "between"
    mark_activity(room, state, 900)
    assert "activity_started_at_ms" not in room


def test_only_meaningful_regular_reward_choice():
    from test_scoring import ledger, played

    assert not settlement_options(ledger(hill=(5, 0, 0)), played(7, (7, 2, 1)))["regular_choice"]
    score = ledger(pool=(20, 15, 10), hill=(5, 0, 0))
    assert settlement_options(score, played(7, (7, 2, 1)))["regular_choice"]
    assert not settlement_options(score, played(7, (6, 3, 1)))["regular_choice"]
    assert not settlement_options(ledger(pool=(20, 15, 10)), played(7, (7, 2, 1)))["regular_choice"]


def test_passout_routes_respect_mandatory_closure():
    from test_scoring import ledger, passouts

    score = ledger(pool=(18, 10, 20), hill=(5, 5, 5), passout=8)
    options = settlement_options(score, passouts((0, 0, 10), level=8))
    # The second player's open pool is credited first, without a hill choice.
    assert options["passout_pending"] == [0]
    assert options["passout_choices"][1] == []
    assert options["passout_choices"][0] == ["hill_first", "help"]
    assert options["passout_targets"][0] == [1]
    chosen = settlement_options(score, passouts((0, 0, 10), level=8), {"0": "help", "1": "pool"})
    assert chosen["passout_pending"] == []
    assert chosen["passout_defaults"] == ["help", "pool", "pool"]


def test_table_theme_admin_only_and_projection(monkeypatch):
    import pytest
    from preferans.online.store import FirestoreRooms, StoreError
    from test_secure_rooms import FakeDB, transactional

    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    svc = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    room = svc.create("a", "experience-create", require_ready=True)["room_id"]
    svc.join(room, "b", "experience-join-b", 0)
    with pytest.raises(StoreError) as err:
        svc.command(room, "b", "experience-denied", 1, "table_theme", {"theme": "glass"})
    assert err.value.code == 403
    svc.command(room, "a", "experience-theme", 1, "table_theme", {"theme": "glass"})
    assert svc.view(room, "b")["table_theme"] == "glass"
    with pytest.raises(StoreError) as err:
        svc.command(room, "a", "experience-invalid", 2, "table_theme", {"theme": "invalid"})
    assert err.value.code == 422
