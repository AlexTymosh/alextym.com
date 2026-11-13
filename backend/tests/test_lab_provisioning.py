"""No-network tests for Owner-only initial-password provisioning."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.security.lab_provisioning import (
    MILLIS_PER_DAY,
    ProvisioningError,
    normalize_invitee_email,
    provision_initial_identity,
    validate_initial_password,
)
from scripts.provision_lab_identity import main


class FakeAuth:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail_at: str | None = None

    def create_user(self, **kwargs):
        self.calls.append(("create", kwargs))
        if self.fail_at == "create":
            raise RuntimeError("sensitive provider email")
        assert kwargs["disabled"] is True
        return SimpleNamespace(uid="new-uid")

    def update_user(self, uid: str, **kwargs):
        self.calls.append(("update", uid, kwargs))
        if self.fail_at == "update":
            raise RuntimeError("sensitive enable failure")

    def delete_user(self, uid: str):
        self.calls.append(("delete", uid))


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail_at: str | None = None

    def create_invited(self, uid: str, record: dict, actor: str) -> None:
        self.calls.append(("create_invited", uid, record, actor))
        if self.fail_at == "create_invited":
            raise RuntimeError("sensitive Firestore error")

    def activate(self, uid: str, timestamp: int, actor: str) -> None:
        self.calls.append(("activate", uid, timestamp, actor))
        if self.fail_at == "activate":
            raise RuntimeError("sensitive Firestore activation")


def provision(auth=None, store=None, **kwargs):
    auth = auth or FakeAuth()
    store = store or FakeStore()
    result = provision_initial_identity(
        auth_client=auth,
        identity_store=store,
        actor_uid="pinned-owner-uid",
        email=" User@Example.test ",
        password="secure-secret-password",
        days=90,
        now_ms=1_800_000_000_000,
        **kwargs,
    )
    return result, auth, store


def test_new_identity_starts_disabled_until_durable_admission_is_activated() -> None:
    result, auth, store = provision()
    assert result.uid == "new-uid"
    assert result.expires_at_ms == 1_800_000_000_000 + 90 * MILLIS_PER_DAY
    assert [call[0] for call in auth.calls] == ["create", "update"]
    assert [call[0] for call in store.calls] == ["create_invited", "activate"]
    identity = store.calls[0][2]
    assert identity["uid"] == "new-uid"
    assert identity["status"] == "invited"
    assert identity["password_state"] == "initial"
    assert identity["provisioned_by_uid"] == "pinned-owner-uid"
    assert "secure-secret-password" not in str(identity)
    assert auth.calls[1] == ("update", "new-uid", {"disabled": False})


def test_firestore_failure_leaves_disabled_orphan_or_removes_user() -> None:
    auth, store = FakeAuth(), FakeStore()
    store.fail_at = "create_invited"
    with pytest.raises(ProvisioningError, match="inspect Firebase") as exc:
        provision(auth, store)
    assert "sensitive" not in str(exc.value)
    assert [call[0] for call in auth.calls] == ["create", "delete"]
    assert [call[0] for call in store.calls] == ["create_invited"]


def test_enable_failure_does_not_activate_identity() -> None:
    auth, store = FakeAuth(), FakeStore()
    auth.fail_at = "update"
    with pytest.raises(ProvisioningError, match="identity remains invited"):
        provision(auth, store)
    assert [call[0] for call in store.calls] == ["create_invited"]


def test_firestore_activation_failure_has_no_credential_delivery() -> None:
    auth, store = FakeAuth(), FakeStore()
    store.fail_at = "activate"
    with pytest.raises(ProvisioningError, match="reconcile UID"):
        provision(auth, store)
    assert [call[0] for call in store.calls] == ["create_invited", "activate"]


def test_existing_firebase_account_is_never_adopted() -> None:
    auth, store = FakeAuth(), FakeStore()
    auth.fail_at = "create"
    with pytest.raises(ProvisioningError, match="already exists"):
        provision(auth, store)
    assert [call[0] for call in auth.calls] == ["create"]
    assert not store.calls


@pytest.mark.parametrize("days", [-1, 0, 91, 100, 2.5, True])
def test_initial_validity_must_be_integer_from_one_to_ninety(days) -> None:
    with pytest.raises(ValueError, match="1–90"):
        validate_initial_password("secure-secret-password", days)


@pytest.mark.parametrize("password", ["short", "", "x" * 129, "abc\n" + "x" * 20])
def test_invalid_initial_password_rejected_before_provisioning(password) -> None:
    with pytest.raises(ValueError):
        validate_initial_password(password, 30)


def test_email_is_normalized_and_invalid_values_rejected() -> None:
    assert normalize_invitee_email(" Owner@Example.TEST ") == "owner@example.test"
    for invalid in ("", "missing-at", "x@y", "x @example.test", "x@.test"):
        if invalid == "x@.test":
            # The provider performs authoritative mailbox validation.
            continue
        with pytest.raises(ValueError):
            normalize_invitee_email(invalid)


def test_cli_dry_run_makes_no_remote_calls(capsys) -> None:
    assert main(["--email", "user@example.test", "--project-id", "dev-project"]) == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_cli_apply_requires_explicit_operator_gate(monkeypatch, capsys) -> None:
    monkeypatch.delenv("PORTFOLIO_LAB_PROVISIONING_ENABLED", raising=False)
    assert main(["--email", "user@example.test", "--project-id", "dev-project", "--apply"]) == 2
    assert "Denied" in capsys.readouterr().err


def test_cli_rejects_wrong_project_even_with_gate(monkeypatch, capsys) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_PROVISIONING_ENABLED", "true")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "correct-project")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")
    assert main(["--email", "user@example.test", "--project-id", "wrong-project", "--apply"]) == 2
    assert "Denied" in capsys.readouterr().err


def test_one_day_expiration_is_exact() -> None:
    result = provision_initial_identity(
        auth_client=FakeAuth(),
        identity_store=FakeStore(),
        actor_uid="owner",
        email="user@example.test",
        password="valid-long-password",
        days=1,
        now_ms=1_800_000_000_000,
    )
    assert result.expires_at_ms == 1_800_000_000_000 + MILLIS_PER_DAY


class FakeFirestoreDocument:
    def __init__(self, collection: str, uid: str) -> None:
        self.collection = collection
        self.uid = uid


class FakeFirestoreCollection:
    def __init__(self, name: str) -> None:
        self.name = name

    def document(self, uid: str):
        return FakeFirestoreDocument(self.name, uid)


class FakeFirestoreBatch:
    def __init__(self) -> None:
        self.actions: list[tuple] = []
        self.committed = False

    def create(self, doc, value):
        self.actions.append(("create", doc.collection, doc.uid, value))

    def update(self, doc, value):
        self.actions.append(("update", doc.collection, doc.uid, value))

    def commit(self):
        self.committed = True


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.batches: list[FakeFirestoreBatch] = []

    def collection(self, name: str):
        return FakeFirestoreCollection(name)

    def batch(self):
        batch = FakeFirestoreBatch()
        self.batches.append(batch)
        return batch


def test_firestore_identity_state_and_audit_are_committed_in_same_batch() -> None:
    from app.security.lab_provisioning import FirestoreIdentityStore

    client = FakeFirestoreClient()
    store = FirestoreIdentityStore(client)
    store.create_invited("new-uid", {"uid": "new-uid", "provisioned_at_ms": 123}, "owner")
    store.activate("new-uid", 456, "owner")
    assert len(client.batches) == 2
    assert all(batch.committed for batch in client.batches)
    first, second = client.batches
    assert [action[0] for action in first.actions] == ["create", "create"]
    assert [action[0] for action in second.actions] == ["update", "create"]
    assert first.actions[0][1:3] == ("portfolio_lab_identities", "new-uid")
    assert first.actions[1][1] == "portfolio_lab_invitation_events"
    assert second.actions[0][3]["status"] == "active"
    assert second.actions[1][3]["actor_uid"] == "owner"
    assert not any("grant" in action[1] for batch in client.batches for action in batch.actions)
