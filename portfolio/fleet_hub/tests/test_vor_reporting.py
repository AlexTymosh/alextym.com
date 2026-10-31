from fleet_hub.services.vor_reporting import _days, _dist, _pct


def test_completed_case_durations():
    assert _days("2026-10-01T10:00:00", "2026-10-03T10:00:00") == 2
    assert _days("invalid", "2026-10-03") is None
    assert _days("2026-10-03", "2026-10-01") == 0


def test_statistical_ranges():
    x = _dist([1, 2, 3, 4, 5, 100], True)
    assert x["retained"] == 5 and x["excluded"] == 1
    assert x["median"] == 3
    assert _pct([1, 2, 3, 4, 5], 0.9) == 4.6
    assert _dist([], False)["median"] is None
