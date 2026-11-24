#!/usr/bin/env python3
"""Offline validation of operator-supplied evidence; does not call providers.

A passing report is not an independent attestation. Never place credentials,
room IDs, SDP/ICE, account identifiers or private cards in the evidence file.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


CORE_CHECKS = (
    "hosted_ci",
    "emulator_roles",
    "origin_and_ticket",
    "private_cards",
    "idempotency",
    "reconnect_and_restart",
    "clock_and_break",
    "full_game_and_ranking",
    "legacy_room",
    "sheet_exit",
    "mobile_landscape",
    "rollback_rehearsed",
    "pricing_and_quota_verified",
    "historical_gaps_resolved_or_owner_approved",
)
MEDIA_CHECKS = (
    "all_three_pairs",
    "explicit_device_consent",
    "device_cleanup",
    "no_media_polling",
    "nat_fallback",
    "audio_video_stability",
)


def nonnegative_int(value):
    return type(value) is int and value >= 0


def evaluate(report: dict) -> dict:
    failures = []
    if not isinstance(report, dict):
        return {"status": "BLOCKED", "failures": ["Invalid report"]}
    if not isinstance(report.get("commit"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", report["commit"]
    ):
        failures.append("Exact candidate commit missing")
    if report.get("environment") not in {"emulator", "staging", "owner-approved-production"}:
        failures.append("Environment missing")
    if report.get("environment") == "emulator":
        failures.append(
            "Emulator alone cannot establish provider pricing/usage or real-device acceptance"
        )
    checks = report.get("checks")
    if not isinstance(checks, dict):
        checks = {}
    for key in CORE_CHECKS:
        if checks.get(key) is not True:
            failures.append(f"Core check not confirmed: {key}")
    if (
        report.get("free_tier_confirmed") is not True
        or report.get("no_paid_dependencies") is not True
    ):
        failures.append("Free-tier operation not confirmed")
    if (
        not isinstance(report.get("device_count"), int)
        or isinstance(report.get("device_count"), bool)
        or report["device_count"] < 3
    ):
        failures.append("Three devices required")
    if (
        not isinstance(report.get("network_count"), int)
        or isinstance(report.get("network_count"), bool)
        or report["network_count"] < 2
    ):
        failures.append("Two networks required")
    runs = report.get("runs")
    if not isinstance(runs, list):
        runs = []
    for hours in (6, 8):
        matching = [r for r in runs if isinstance(r, dict) and r.get("hours") == hours]
        if len(matching) != 1:
            failures.append(f"Exactly one {hours}h run required")
            continue
        run = matching[0]
        prefix = f"{hours}h"
        for name in (
            "elapsed_seconds",
            "session_reads",
            "session_writes",
            "daily_reads",
            "daily_writes",
            "daily_deletes",
            "latency_samples",
            "unexpected_disconnects",
            "storage_errors",
            "memory_growth_bytes",
        ):
            if not nonnegative_int(run.get(name)):
                failures.append(f"{prefix}: missing/invalid {name}")

        def exceeds(name, limit):
            return nonnegative_int(run.get(name)) and run[name] > limit

        if not nonnegative_int(run.get("elapsed_seconds")) or run["elapsed_seconds"] < hours * 3600:
            failures.append(f"{prefix}: insufficient elapsed time")
        if hours == 6:
            if exceeds("session_reads", 15_000):
                failures.append("6h: read target exceeded")
            if exceeds("session_writes", 10_000):
                failures.append("6h: write target exceeded")
        # Daily totals are measured site-wide, maximum for any quota day touched.
        for name, limit in (
            ("daily_reads", 50_000),
            ("daily_writes", 20_000),
            ("daily_deletes", 20_000),
        ):
            if exceeds(name, limit):
                failures.append(f"{prefix}: daily quota exceeded: {name}")
        for session, daily in (
            ("session_reads", "daily_reads"),
            ("session_writes", "daily_writes"),
        ):
            # On a single quota day a session cannot exceed the site total.
            if (
                run.get("single_quota_day") is True
                and nonnegative_int(run.get(session))
                and nonnegative_int(run.get(daily))
                and run[session] > run[daily]
            ):
                failures.append(f"{prefix}: inconsistent session and daily totals: {session}")
        if not nonnegative_int(run.get("latency_samples")) or run["latency_samples"] < 100:
            failures.append(f"{prefix}: fewer than 100 measured latency samples")
        previous = -1
        for name in ("p50_ms", "p95_ms", "p99_ms"):
            value = run.get(name)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value < 0
                or value < previous
            ):
                failures.append(f"{prefix}: invalid percentile {name}")
            else:
                previous = value
        if type(run.get("p95_ms")) in (int, float) and run["p95_ms"] > 500:
            failures.append(f"{prefix}: p95 latency target exceeded")
        if run.get("storage_errors") != 0:
            failures.append(f"{prefix}: storage errors not cleared")
        for key in (
            "provider_usage_verified",
            "memory_stable",
            "no_duplicate_actions",
            "real_duration",
            "reserve_verified",
        ):
            if run.get(key) is not True:
                failures.append(f"{prefix}: {key} not confirmed")
        if not isinstance(run.get("evidence_ref"), str) or not run["evidence_ref"].strip():
            failures.append(f"{prefix}: evidence reference missing")
    media = report.get("media")
    if not isinstance(media, dict):
        media = {}
    media_failures = [key for key in MEDIA_CHECKS if media.get(key) is not True]
    media_status = "READY_FOR_REVIEW" if not media_failures else "BLOCKED"
    return {
        "status": "READY_FOR_OWNER_REVIEW" if not failures else "BLOCKED",
        "failures": failures,
        "media_status": media_status,
        "media_failures": media_failures,
        "note": "Operator-supplied evidence only; never an automated deployment approval.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.report.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "READY_FOR_OWNER_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
