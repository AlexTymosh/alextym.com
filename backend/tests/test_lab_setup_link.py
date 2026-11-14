"""No-network tests for private one-time setup links and invite admission."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.security.lab_provisioning import ProvisioningError
from app.security.lab_setup_link import (
    build_private_action_link,
    create_setup_identity,
    verify_existing_setup_identity,
)
from scripts.generate_lab_setup_link import main


def test_reset_code_transferred_into_fragment_not_http_query() -> None:
    link = build_private_action_link(
        "https://project.firebaseapp.com/__/auth/action?mode=resetPassword&apiKey=public&oobCode=abcDEF123_-1",
        "https://preview.example.test",
        "firebase-uid",
    )
    assert (
        link
        == "https://preview.example.test/lab/password/reset#uid=firebase-uid&oobCode=abcDEF123_-1"
    )
    assert "?" not in link


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.test",
        "https://example.test/folder",
        "https://example.test?foo=bar",
        "https://user:pass@example.test",
        "https://example.test#fragment",
        "javascript:alert(1)",
    ],
)
def test_untrusted_origin_rejected(origin: str) -> None:
    with pytest.raises(ValueError):
        build_private_action_link(
            "https://project.firebaseapp.com/x?mode=resetPassword&oobCode=abcdefghijklmn",
            origin,
            "firebase-uid",
        )


def test_local_http_only_when_explicitly_allowed() -> None:
    src = "https://project.firebaseapp.com/x?mode=resetPassword&oobCode=abcdefghijklmn"
    with pytest.raises(ValueError):
        build_private_action_link(src, "http://localhost:3000", "firebase-uid")
    assert build_private_action_link(
        src, "http://localhost:3000", "firebase-uid", allow_http_local=True
    ).startswith("http://localhost:3000/lab/password/reset#")
    with pytest.raises(ValueError):
        build_private_action_link(src, "http://evil.test", "firebase-uid", allow_http_local=True)


@pytest.mark.parametrize(
    "source",
    [
        "https://project.firebaseapp.com/x?mode=verifyEmail&oobCode=abcdefghijklmn",
        "https://project.firebaseapp.com/x?mode=resetPassword&oobCode=x",
        "https://project.firebaseapp.com/x?mode=resetPassword",
        "http://project.firebaseapp.com/x?mode=resetPassword&oobCode=abcdefghijklmn",
        "https://project.firebaseapp.com/x?mode=resetPassword&oobCode=a%20b%20c%20d%20e",
    ],
)
def test_unsafe_reset_codes_rejected(source: str) -> None:
    with pytest.raises(ProvisioningError):
        build_private_action_link(source, "https://preview.example.test", "firebase-uid")


class FakeAuth:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail_at: str | None = None

    def create_user(self, **kwargs):
        self.calls.append(("create", kwargs))
        if self.fail_at == "create":
            raise RuntimeError("secret email")
        return SimpleNamespace(uid="new-user")

    def update_user(self, uid: str, **kwargs):
        self.calls.append(("update", uid, kwargs))
        if self.fail_at == "update":
            raise RuntimeError("secret provider")


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail: bool = False

    def create_invited(self, uid, record, actor):
        self.calls.append((uid, record, actor))
        if self.fail:
            raise RuntimeError("secret db")


def test_create_setup_identity_keeps_uid_invited_until_code_redeemed() -> None:
    auth, store = FakeAuth(), FakeStore()
    result = create_setup_identity(
        auth_client=auth,
        identity_store=store,
        actor_uid="owner",
        email=" New@Example.test ",
        now_ms=1_800_000_000_000,
    )
    assert (result.uid, result.created) == ("new-user", True)
    assert auth.calls[0][1]["disabled"] is True
    assert auth.calls[0][1]["email"] == "new@example.test"
    assert len(auth.calls[0][1]["password"]) >= 40
    assert auth.calls[1] == ("update", "new-user", {"disabled": False})
    doc = store.calls[0][1]
    assert (doc["status"], doc["password_state"]) == ("invited", "none")
    assert auth.calls[0][1]["password"] not in str(doc)


def test_firestore_failure_prevents_enable() -> None:
    auth, store = FakeAuth(), FakeStore()
    store.fail = True
    with pytest.raises(ProvisioningError, match="inspect disabled UID"):
        create_setup_identity(
            auth_client=auth,
            identity_store=store,
            actor_uid="owner",
            email="new@example.test",
            now_ms=1_800_000_000_000,
        )
    assert [c[0] for c in auth.calls] == ["create"]


def test_enable_failure_does_not_make_record_active() -> None:
    auth, store = FakeAuth(), FakeStore()
    auth.fail_at = "update"
    with pytest.raises(ProvisioningError, match="inspect invited UID"):
        create_setup_identity(
            auth_client=auth,
            identity_store=store,
            actor_uid="owner",
            email="new@example.test",
            now_ms=1_800_000_000_000,
        )
    assert store.calls[0][1]["status"] == "invited"


@pytest.mark.parametrize(
    "record,user",
    [
        (
            {"schema_version": 1, "uid": "u", "status": "revoked", "password_state": "initial"},
            SimpleNamespace(uid="u", disabled=False),
        ),
        (
            {"schema_version": 1, "uid": "other", "status": "active", "password_state": "initial"},
            SimpleNamespace(uid="u", disabled=False),
        ),
        (
            {"schema_version": 1, "uid": "u", "status": "active", "password_state": "user_set"},
            SimpleNamespace(uid="u", disabled=True),
        ),
        (
            {"schema_version": 1, "uid": "owner", "status": "active", "password_state": "initial"},
            SimpleNamespace(uid="owner", disabled=False),
        ),
        (None, SimpleNamespace(uid="u", disabled=False)),
    ],
)
def test_existing_only_admitted_known_eligible_uid(record, user):
    with pytest.raises(ProvisioningError):
        verify_existing_setup_identity(auth_user=user, record=record, owner_uid="owner")


def test_existing_active_and_invited_can_recover() -> None:
    for status in ("active", "invited"):
        assert (
            verify_existing_setup_identity(
                auth_user=SimpleNamespace(uid="u", disabled=False),
                record={
                    "schema_version": 1,
                    "uid": "u",
                    "status": status,
                    "password_state": "none",
                },
                owner_uid="owner",
            )
            == "u"
        )


def test_cli_is_dry_run_by_default(capsys) -> None:
    assert (
        main(
            [
                "--email",
                "invite@example.test",
                "--project-id",
                "dev-project",
                "--origin",
                "https://preview.example.test",
            ]
        )
        == 0
    )
    assert "DRY RUN" in capsys.readouterr().out


def test_cli_needs_owner_gate(monkeypatch, capsys) -> None:
    monkeypatch.delenv("PORTFOLIO_LAB_PROVISIONING_ENABLED", raising=False)
    result = main(
        [
            "--email",
            "invite@example.test",
            "--project-id",
            "dev-project",
            "--origin",
            "https://preview.example.test",
            "--apply",
        ]
    )
    assert result == 2
    assert "Denied" in capsys.readouterr().err


def test_new_setup_record_and_audit_share_atomic_batch() -> None:
    from app.security.lab_setup_link import FirestoreSetupIdentityStore

    class Doc:
        def __init__(self, collection: str, uid: str) -> None:
            self.collection, self.uid = collection, uid

    class Collection:
        def __init__(self, name: str) -> None:
            self.name = name

        def document(self, uid: str):
            return Doc(self.name, uid)

    class Batch:
        def __init__(self) -> None:
            self.calls = []
            self.committed = False

        def create(self, doc, value):
            self.calls.append((doc.collection, value))

        def commit(self):
            self.committed = True

    class Firestore:
        def __init__(self) -> None:
            self.batch_obj = Batch()

        def collection(self, name: str):
            return Collection(name)

        def batch(self):
            return self.batch_obj

    db = Firestore()
    store = FirestoreSetupIdentityStore(db)
    record = {"uid": "new-uid", "provisioned_at_ms": 1_800_000_000_000}
    store.create_invited("new-uid", record, "owner")
    assert db.batch_obj.committed
    assert [entry[0] for entry in db.batch_obj.calls] == [
        "portfolio_lab_identities",
        "portfolio_lab_invitation_events",
    ]
    assert db.batch_obj.calls[1][1]["action"] == "password_setup_identity_invited"
