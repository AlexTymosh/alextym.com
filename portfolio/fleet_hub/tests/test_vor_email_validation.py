"""Linear-time email validation and Fleet VOR contacts API regression tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api.vor import router, valid_email


@pytest.mark.parametrize(
    "email",
    [
        "alex@example.com",
        "alex.tymoshenko@scas.nhs.uk",
        "fleet+alerts@mail.alextym.com",
        "o'connor@workshop.example",
        "a@b.co",
    ],
)
def test_valid_common_email_addresses(email: str) -> None:
    assert valid_email(email)


@pytest.mark.parametrize(
    "email",
    [
        "",
        "plainaddress",
        "@example.com",
        "alex@",
        "alex@example",
        "alex@example..com",
        "alex@.example.com",
        "alex@example.com.",
        ".alex@example.com",
        "alex..team@example.com",
        "alex@example-.com",
        "alex@-example.com",
        "alex @example.com",
        "alex@example.com\nBcc:unwanted@example.com",
        "alex\t@example.com",
        "alex\x00@example.com",
        "alex@@example.com",
        "alex@exam_ple.com",
        "üser@example.com",
        ("a" * 65) + "@example.com",
        "alex@" + ("a" * 64) + ".com",
        ("!@!." + "!." * 90 + "example"),
        "a" * 255 + "@example.com",
    ],
)
def test_reject_invalid_or_adversarial_addresses(email: str) -> None:
    assert not valid_email(email)


@pytest.fixture
def authenticated_client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "test-validation-password")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "fleet-email-validation.sqlite3"))
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.post("/api/vor/login", json={"password": "test-validation-password"})
        assert response.status_code == 200, response.text
        yield client


def test_contacts_api_rejects_adversarial_email(authenticated_client: TestClient) -> None:
    bad_email = "!@!." + "!." * 90 + "example"
    response = authenticated_client.post(
        "/api/vor/contacts",
        json={"name": "Bad address", "email": bad_email, "role": "external"},
    )
    assert response.status_code == 422, response.text

    contacts = authenticated_client.get("/api/vor/bootstrap").json()["contacts"]
    assert contacts
    response = authenticated_client.post(
        f"/api/vor/contacts/{contacts[0]['id']}/update",
        json={"name": "Bad address", "email": bad_email, "role": "external"},
    )
    assert response.status_code == 422, response.text


def test_contacts_api_accepts_standard_email(authenticated_client: TestClient) -> None:
    response = authenticated_client.post(
        "/api/vor/contacts",
        json={"name": "Fleet Test", "email": "fleet+test@example.co.uk", "role": "external"},
    )
    assert response.status_code == 200, response.text
    assert isinstance(response.json()["id"], int)
