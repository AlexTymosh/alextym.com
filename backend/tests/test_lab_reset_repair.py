"""Offline fail-closed contract tests for interrupted reset repair."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.security.lab_provisioning import ProvisioningError
from app.security.lab_reset_repair import is_repairable_pending_reset, repair_interrupted_reset
from scripts.repair_lab_password_reset import main


UID = "invited-uid"
OWNER = "owner-uid"
RECORD = {
    "schema_version": 1,
    "uid": UID,
    "status": "active",
    "password_state": "reset_pending",
}


class FakeAuth:
    def __init__(self):
        self.calls: list[str] = []
        self.disabled = False
        self.fail_revoke = False

    def get_user(self, uid):
        self.calls.append("get_user")
        return SimpleNamespace(uid=uid, disabled=self.disabled)

    def revoke_refresh_tokens(self, uid):
        self.calls.append("revoke")
        if self.fail_revoke:
            raise RuntimeError("private token")


class FakeStore:
    def __init__(self, record=None):
        self.record = RECORD.copy() if record is None else record
        self.calls: list[str] = []

    def load(self, uid):
        self.calls.append("load")
        return self.record

    def mark_password_unavailable(self, uid, owner, now, pending_record):
        self.calls.append("repair")
        assert (uid, owner, now) == (UID, OWNER, 1_800_000_000_000)
        assert pending_record["password_state"] == "reset_pending"
        self.record["password_state"] = "none"


def repair(auth=None, store=None):
    auth = auth or FakeAuth()
    store = store or FakeStore()
    repair_interrupted_reset(
        auth_client=auth,
        identity_store=store,
        owner_uid=OWNER,
        uid=UID,
        now_ms=1_800_000_000_000,
    )
    return auth, store


def test_repair_revokes_before_unblocking_recovery():
    auth, store = repair()
    assert auth.calls == ["get_user", "revoke"]
    assert store.calls == ["load", "repair"]
    assert store.record["password_state"] == "none"


@pytest.mark.parametrize("state", ["initial", "user_set", "none", "revoked"])
def test_unexpected_password_state_denied(state):
    store = FakeStore({**RECORD, "password_state": state})
    with pytest.raises(ProvisioningError):
        repair(store=store)
    assert store.calls == ["load"]


@pytest.mark.parametrize("status", ["revoked", "disabled", "pending"])
def test_non_active_invitation_denied(status):
    store = FakeStore({**RECORD, "status": status})
    with pytest.raises(ProvisioningError):
        repair(store=store)
    assert store.calls == ["load"]


def test_invited_pending_identity_can_be_repaired():
    assert is_repairable_pending_reset(UID, OWNER, {**RECORD, "status": "invited"})


def test_revocation_failure_does_not_write():
    auth = FakeAuth()
    auth.fail_revoke = True
    store = FakeStore()
    with pytest.raises(ProvisioningError, match="not confirmed") as exc:
        repair(auth, store)
    assert "private" not in str(exc.value)
    assert store.calls == ["load"]


def test_disabled_auth_user_never_repaired_implicitly():
    auth = FakeAuth()
    auth.disabled = True
    store = FakeStore()
    with pytest.raises(ProvisioningError, match="enabled"):
        repair(auth, store)
    assert store.calls == ["load"]


def test_missing_uid_or_owner_denied():
    for uid, owner in [(OWNER, OWNER), ("", OWNER), ("wrong/name", OWNER), (UID, "")]:
        assert not is_repairable_pending_reset(uid, owner, RECORD)


def test_cli_dry_run_does_not_connect(capsys):
    assert main(["--uid", UID, "--project-id", "dev-only"]) == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_cli_apply_requires_explicit_operator_gate(monkeypatch):
    monkeypatch.delenv("PORTFOLIO_LAB_PROVISIONING_ENABLED", raising=False)
    assert main(["--uid", UID, "--project-id", "dev-only", "--apply"]) == 2


def test_cli_refuses_wrong_project(monkeypatch):
    monkeypatch.setenv("PORTFOLIO_LAB_PROVISIONING_ENABLED", "true")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "dev-only")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", OWNER)
    assert main(["--uid", UID, "--project-id", "prod-wrong", "--apply"]) == 2


def test_firestore_repair_revalidates_state_and_audits_atomically(monkeypatch):
    import sys
    from types import ModuleType

    from app.security.lab_reset_repair import FirestoreResetRepairStore

    delete_sentinel = object()
    fake_firestore = ModuleType("google.cloud.firestore")
    fake_firestore.DELETE_FIELD = delete_sentinel
    fake_firestore.transactional = lambda function: function
    from google import cloud

    monkeypatch.setitem(sys.modules, "google.cloud.firestore", fake_firestore)
    monkeypatch.setattr(cloud, "firestore", fake_firestore, raising=False)

    class Snapshot:
        exists = True

        def to_dict(self):
            return RECORD.copy()

    class Document:
        def __init__(self, collection):
            self.collection = collection

        def get(self, **kwargs):
            return Snapshot()

    class Collection:
        def __init__(self, name):
            self.name = name

        def document(self, *_):
            return Document(self.name)

    class Transaction:
        def __init__(self):
            self.actions = []

        def update(self, doc, data):
            self.actions.append(("update", doc.collection, data))

        def create(self, doc, data):
            self.actions.append(("create", doc.collection, data))

    class Client:
        def __init__(self):
            self.tx = Transaction()

        def collection(self, name):
            return Collection(name)

        def transaction(self):
            return self.tx

    client = Client()
    FirestoreResetRepairStore(client).mark_password_unavailable(
        UID, OWNER, 1_800_000_000_000, RECORD
    )
    assert len(client.tx.actions) == 2
    update, audit = client.tx.actions
    assert update[0:2] == ("update", "portfolio_lab_identities")
    assert update[2]["password_state"] == "none"
    assert update[2]["password_reset_started_at_ms"] is delete_sentinel
    assert audit[0:2] == ("create", "portfolio_lab_invitation_events")
    assert audit[2]["actor_uid"] == OWNER
    assert audit[2]["action"] == "password_reset_repaired_requires_new_link"


def test_repair_transaction_rejects_changed_record(monkeypatch):
    import sys
    from types import ModuleType

    from app.security.lab_reset_repair import FirestoreResetRepairStore

    fake_firestore = ModuleType("google.cloud.firestore")
    fake_firestore.DELETE_FIELD = object()
    fake_firestore.transactional = lambda function: function
    from google import cloud

    monkeypatch.setitem(sys.modules, "google.cloud.firestore", fake_firestore)
    monkeypatch.setattr(cloud, "firestore", fake_firestore, raising=False)

    class Snapshot:
        exists = True

        def to_dict(self):
            return {**RECORD, "status": "revoked"}

    class Document:
        def get(self, **kwargs):
            return Snapshot()

    class Collection:
        def document(self, *_):
            return Document()

    class Transaction:
        def update(self, *_):
            pytest.fail("Revoked identity must not be updated")

        def create(self, *_):
            pytest.fail("Revoked identity must not create audit event")

    class Client:
        def collection(self, *_):
            return Collection()

        def transaction(self):
            return Transaction()

    with pytest.raises(ProvisioningError, match="changed"):
        FirestoreResetRepairStore(Client()).mark_password_unavailable(
            UID, OWNER, 1_800_000_000_000, RECORD
        )
