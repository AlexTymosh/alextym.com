"""Bounded, append-only template revisions using existing numerical rules."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict

from preferans.domain.rulesets import Ruleset
from preferans.online.controls import configure_policy

BASE_ID = "zaporizhzhia-classic"
BASE_POLICY = {"counter_seconds": 180, "counter_multiplier": 3, "undo_seconds": 120}
# Only values demonstrably consumed by the current engine; structural obligations stay fixed.
FIELDS = {
    "pool_target",
    "regular_costs",
    "misere_cost",
    "passout_costs",
    "half_vist_award",
    "trick_vist_multiplier",
    "consolation_multiplier",
    "help_vists_per_point",
    "surplus_vists_per_opponent",
    "hill_vist_numerator",
    "hill_vist_denominator",
}
ID = re.compile(r"[a-f0-9]{32}")


def parameters(rules: Ruleset) -> dict:
    values = asdict(rules)
    return {
        key: list(values[key]) if isinstance(values[key], tuple) else values[key]
        for key in sorted(FIELDS)
    }


def validated(identifier: str, version: int, values: dict, policy: dict) -> tuple[Ruleset, dict]:
    if not isinstance(values, dict) or set(values) != FIELDS:
        raise ValueError("Invalid ruleset fields")
    parsed = dict(values)
    for key in ("regular_costs", "passout_costs"):
        raw = parsed[key]
        if not isinstance(raw, list):
            raise ValueError("Expected a list of costs")
        parsed[key] = tuple(raw)
    for key, raw in parsed.items():
        numbers = raw if isinstance(raw, tuple) else (raw,)
        maximum = 1000 if key == "pool_target" else 100
        if any(type(n) is not int or not 1 <= n <= maximum for n in numbers):
            raise ValueError("Ruleset parameter outside allowed range")
    rules = Ruleset(identifier=identifier, version=version, **parsed)
    if any(a >= b for a, b in zip(rules.regular_costs, rules.regular_costs[1:])):
        raise ValueError("Contract costs must increase")
    if any(a >= b for a, b in zip(rules.passout_costs, rules.passout_costs[1:])):
        raise ValueError("Passout costs must increase")
    if rules.help_vists_per_point != 2 * rules.surplus_vists_per_opponent:
        raise ValueError("Help and surplus values must conserve accounting")
    controls: dict = {}
    configure_policy(controls, policy)
    return rules, controls["policy"]


def snapshot_hash(rules: Ruleset, policy: dict) -> str:
    payload = json.dumps(
        {"rules": asdict(rules), "policy": policy},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def base() -> dict:
    return {
        "id": BASE_ID,
        "version": 1,
        "name": "\u041f\u0440\u0435\u0444\u0435\u0440\u0430\u043d\u0441 \u043f\u043e-\u0437\u0430\u043f\u043e\u0440\u043e\u0436\u0441\u043a\u0438 — \u041a\u043b\u0430\u0441\u0441\u0438\u0447\u0435\u0441\u043a\u0438\u0439",
        "description": "",
        "parameters": parameters(Ruleset()),
        "policy": BASE_POLICY.copy(),
        "sha256": Ruleset().fingerprint(),
        "snapshot_hash": snapshot_hash(Ruleset(), BASE_POLICY),
    }


def public(record: dict) -> dict:
    return {
        key: record[key]
        for key in (
            "id",
            "version",
            "name",
            "description",
            "parameters",
            "policy",
            "sha256",
            "snapshot_hash",
        )
    }


def load(tx, db, identifier: object, version: object) -> dict:
    if type(version) is not int or version < 1:
        raise ValueError("Invalid version")
    if identifier == BASE_ID and version == 1:
        return base()
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise ValueError("Invalid template ID")
    snap = (
        db.collection("preferans_rulesets")
        .document(identifier)
        .collection("versions")
        .document(str(version))
        .get(transaction=tx, timeout=5.0)
    )
    if not snap.exists:
        raise ValueError("Template revision not found")
    return public(snap.to_dict())


def list_templates(db) -> dict:
    rows = db.collection("preferans_rulesets").limit(101).stream(timeout=5.0)
    templates = [public(s.to_dict()) for s in rows]
    return {"templates": [base(), *templates[:100]], "truncated": len(templates) > 100}


def save(db, fs, uid: str, body: dict, now: int) -> dict:
    if set(body) != {"id", "expected_version", "name", "description", "parameters", "policy"}:
        raise ValueError("Invalid template body")
    identifier, expected = body["id"], body["expected_version"]
    if type(expected) is not int or expected < 0:
        raise ValueError("Invalid template version")
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise ValueError("Copy the base template instead of modifying it")
    name, description = body["name"], body["description"]
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 80
        or not isinstance(description, str)
        or len(description) > 240
    ):
        raise ValueError("Invalid template name or description")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name + description):
        raise ValueError("Invalid template text")
    rules, policy = validated(identifier, expected + 1, body["parameters"], body["policy"])
    ref = db.collection("preferans_rulesets").document(identifier)
    tx = db.transaction()

    @fs.transactional
    def commit(transaction):
        snap = ref.get(transaction=transaction, timeout=5.0)
        previous = snap.to_dict() if snap.exists else None
        candidate = {
            "id": identifier,
            "version": expected + 1,
            "name": name.strip(),
            "description": description.strip(),
            "parameters": parameters(rules),
            "policy": policy,
            "sha256": rules.fingerprint(),
            "snapshot_hash": snapshot_hash(rules, policy),
        }
        # Repeating exactly the same save after a lost HTTP response is safe.
        if previous and public(previous) == candidate:
            return candidate
        if (previous["version"] if previous else 0) != expected:
            raise ValueError("Template changed; reload")
        record = {
            **candidate,
            "schema_version": 1,
            "owner_uid": previous["owner_uid"] if previous else uid,
            "created_at_ms": previous["created_at_ms"] if previous else now,
            "updated_at_ms": now,
            "status": "active",
        }
        transaction.create(ref.collection("versions").document(str(record["version"])), record)
        transaction.set(ref, record)
        return public(record)

    return commit(tx)
