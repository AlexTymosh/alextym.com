from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "release_evidence", Path(__file__).parents[1] / "scripts" / "release_evidence.py"
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def report():
    # Synthetic pass fixture only. Never use as acceptance evidence.
    return {
        "commit": "a" * 40,
        "environment": "staging",
        "checks": dict.fromkeys(module.CORE_CHECKS, True),
        "free_tier_confirmed": True,
        "no_paid_dependencies": True,
        "device_count": 3,
        "network_count": 2,
        "media": dict.fromkeys(module.MEDIA_CHECKS, True),
        "runs": [
            {
                "hours": h,
                "elapsed_seconds": h * 3600,
                "session_reads": 10_000,
                "session_writes": 6_000,
                "daily_reads": 25_000,
                "daily_writes": 10_000,
                "daily_deletes": 0,
                "latency_samples": 100,
                "unexpected_disconnects": 0,
                "storage_errors": 0,
                "memory_growth_bytes": 0,
                "p50_ms": 100,
                "p95_ms": 400,
                "p99_ms": 800,
                "single_quota_day": True,
                "provider_usage_verified": True,
                "memory_stable": True,
                "no_duplicate_actions": True,
                "real_duration": True,
                "reserve_verified": True,
                "evidence_ref": "SYNTHETIC_FIXTURE",
            }
            for h in (6, 8)
        ],
    }


def test_missing_evidence_is_blocked():
    assert module.evaluate({})["status"] == "BLOCKED"
    assert module.evaluate({})["media_status"] == "BLOCKED"


def test_synthetic_complete_report_only_ready_for_review():
    assert module.evaluate(report())["status"] == "READY_FOR_OWNER_REVIEW"


def test_overspend_and_short_soak_fail_even_with_green_checks():
    r = report()
    r["runs"][0].update(session_writes=10001, elapsed_seconds=120, p95_ms=501)
    result = module.evaluate(r)
    assert result["status"] == "BLOCKED"
    assert any("write target" in f for f in result["failures"])
    assert any("elapsed" in f for f in result["failures"])
    assert any("latency target" in f for f in result["failures"])


def test_media_independent_of_core_and_emulator_not_release_evidence():
    r = report()
    r["media"]["all_three_pairs"] = False
    assert module.evaluate(r)["status"] == "READY_FOR_OWNER_REVIEW"
    assert module.evaluate(r)["media_status"] == "BLOCKED"
    r["environment"] = "emulator"
    assert module.evaluate(r)["status"] == "BLOCKED"
