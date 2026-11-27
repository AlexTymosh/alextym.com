from preferans.online import discard_gag


def test_extended_redeal_timeline_is_authoritative_and_consumed_once():
    assert discard_gag.GAG_FAKE_MS == 10_100
    assert discard_gag.GAG_TOTAL_MS == 14_000
    for seat in range(3):
        control = {}
        discard_gag.record_discard(control, "old", seat, 1000, True)
        assert discard_gag.begin(control, "old", "new", 2000)
        assert discard_gag.active(control, "new", 15_999)
        assert not discard_gag.active(control, "new", 16_000)
        assert discard_gag.project(control, "new", auction=True) == {
            "redeal_gag": {"seat": seat, "at_ms": 2000}
        }
        assert not discard_gag.begin(control, "new", "next", 17_000)
        assert not control
