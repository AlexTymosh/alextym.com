"""Run Portfolio Lab against Next.js, FastAPI and the Firebase demo emulators."""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from firebase_admin import auth, firestore

from app.security.firebase_identity import _firebase_app
from app.security.lab_provisioning import FirestoreIdentityStore, provision_initial_identity
from scripts import generate_lab_setup_link, repair_lab_password_reset
from scripts.provision_lab_identity import _AuthClient


PROJECT = "demo-portfolio-lab"
OWNER = "lab-emulator-owner"
SITE = "http://localhost:14300"
BACKEND = "http://127.0.0.1:14800"
COOKIE = "portfolio_lab_session"


class SmokeFailure(Exception):
    pass


def check(name: str, passed: bool, *, status: int | None = None) -> None:
    if not passed:
        detail = "" if status is None else f" (HTTP {status})"
        raise SmokeFailure(f"{name}{detail}")
    print(f"PASS {name}", flush=True)


def claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def wait_past(auth_time: int) -> None:
    while int(time.time()) <= auth_time:
        time.sleep(0.1)


def run() -> None:
    localhost = r"127\.0\.0\.1:[0-9]{1,5}"
    if (
        os.getenv("FIREBASE_PROJECT_ID") != PROJECT
        or os.getenv("PORTFOLIO_LAB_OWNER_UID") != OWNER
        or os.getenv("PORTFOLIO_LAB_PROVISIONING_ENABLED") != "true"
        or not all(
            re.fullmatch(localhost, os.getenv(name, ""))
            for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST")
        )
    ):
        raise SmokeFailure("this runner requires both localhost Firebase demo emulators")
    auth_base = f"http://{os.environ['FIREBASE_AUTH_EMULATOR_HOST']}"
    app = _firebase_app()
    db = firestore.client(app=app)
    accounts = _AuthClient(auth, app)
    identities = db.collection("portfolio_lab_identities")
    run_id = secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    replacement = secrets.token_urlsafe(24)
    owner_email = f"owner-{run_id}@example.test"
    unknown_email = f"unknown-{run_id}@example.test"
    invitee_email = f"invitee-{run_id}@example.test"
    with httpx.Client(timeout=35, trust_env=False) as http:

        def password_sign_in(email: str, secret: str) -> httpx.Response:
            return http.post(
                f"{auth_base}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={PROJECT}",
                json={"email": email, "password": secret, "returnSecureToken": True},
            )

        def exchange(token: str, origin: str = SITE) -> httpx.Response:
            return http.post(
                f"{SITE}/lab/session", headers={"Origin": origin}, json={"idToken": token}
            )

        def direct(token: str | None = None, scheme: str = "Bearer") -> httpx.Response:
            headers = {"Authorization": f"{scheme} {token}"} if token else {}
            return http.get(f"{BACKEND}/api/lab/identity", headers=headers)

        def browser_session(cookie: str, path: str = "/lab/session") -> httpx.Response:
            return http.get(f"{SITE}{path}", headers={"Cookie": f"{COOKIE}={cookie}"})

        def make_link(email: str, *, create: bool = False) -> tuple[str, str]:
            args = ["--email", email, "--project-id", PROJECT, "--origin", SITE, "--apply"]
            if create:
                args.append("--create-user")
            with redirect_stdout(StringIO()) as output:
                result = generate_lab_setup_link.main(args)
            check("Owner CLI issued private setup link", result == 0)
            link = next(line for line in output.getvalue().splitlines() if line.startswith(SITE))
            parts = urlsplit(link)
            check("setup code appears only in fragment", not parts.query and bool(parts.fragment))
            fragment = parse_qs(parts.fragment)
            return fragment["uid"][0], fragment["oobCode"][0]

        def redeem(uid: str, code: str, new_password: str) -> httpx.Response:
            return http.post(
                f"{SITE}/lab/password/reset/action",
                headers={"Origin": SITE},
                json={"uid": uid, "oobCode": code, "newPassword": new_password},
            )

        def oauth(provider: str, subject: str, *, link_token: str | None = None) -> httpx.Response:
            credential = urlencode(
                {
                    "providerId": provider,
                    "id_token": json.dumps(
                        {
                            "sub": subject,
                            "email": f"{subject}@example.test",
                            "email_verified": True,
                        }
                    ),
                }
            )
            body = {"requestUri": SITE, "postBody": credential, "returnSecureToken": True}
            if link_token:
                body["idToken"] = link_token
            return http.post(
                f"{auth_base}/identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={PROJECT}",
                json=body,
            )

        owner = (
            auth.get_user(OWNER, app=app)
            if any(user.uid == OWNER for user in auth.list_users(app=app).users)
            else auth.create_user(uid=OWNER, email=owner_email, password=password, app=app)
        )
        auth.update_user(OWNER, email=owner_email, password=password, app=app)
        check("pinned Owner UID configured", owner.uid == OWNER)
        owner_response = password_sign_in(owner_email, password)
        check("Firebase Owner password sign-in", owner_response.status_code == 200)
        owner_token = owner_response.json()["idToken"]
        response = exchange(owner_token)
        check("Owner session issued", response.status_code == 200, status=response.status_code)
        owner_cookie = response.cookies[COOKIE]
        attributes = response.headers["Set-Cookie"].lower()
        check(
            "session TTL and HttpOnly Strict cookie",
            all(
                attr in attributes
                for attr in ("httponly", "samesite=strict", "path=/", "max-age=432000")
            ),
        )
        check(
            "valid session through Next.js and FastAPI",
            browser_session(owner_cookie, "/lab/api/identity").status_code == 200,
        )
        check("direct valid ID token", direct(owner_token).status_code == 200)
        check(
            "direct missing, malformed and wrong credential scheme",
            all(
                response.status_code == 401
                for response in (
                    direct(),
                    direct("bad-token"),
                    direct(owner_cookie),
                    direct(owner_token, "FirebaseSession"),
                )
            ),
        )
        check(
            "missing session and cross-origin exchange rejected",
            (
                browser_session("malformed").status_code == 401
                and exchange(owner_token, "https://cross-origin.example.test").status_code == 403
                and http.delete(f"{SITE}/lab/session", headers={"Origin": "null"}).status_code
                == 403
            ),
        )
        foreign = http.post(
            f"{SITE}/lab/session/link", headers={"Origin": "https://cross-origin.example.test"}
        )
        check("cross-origin provider binding rejected", foreign.status_code == 403)
        check(
            "streamed oversized JSON rejected",
            http.post(
                f"{SITE}/lab/session",
                headers={"Origin": SITE, "Content-Type": "application/json"},
                content=iter([b'{"idToken":"', b"a" * 11_000, b'"}']),
            ).status_code
            == 413,
        )
        auth.create_user(email=unknown_email, password=password, app=app)
        unknown_token = password_sign_in(unknown_email, password).json()["idToken"]
        check(
            "valid but uninvited UID denied on both hosts",
            (
                exchange(unknown_token).status_code == 403
                and direct(unknown_token).status_code == 403
            ),
        )

        identity = provision_initial_identity(
            auth_client=accounts,
            identity_store=FirestoreIdentityStore(db),
            actor_uid=OWNER,
            email=invitee_email,
            password=password,
            days=1,
            now_ms=int(time.time() * 1000),
        )
        user_ref = identities.document(identity.uid)
        check(
            "Owner provisioning commits active initial password",
            user_ref.get().to_dict()["status"] == "active",
        )
        token = password_sign_in(invitee_email, password).json()["idToken"]
        repeated = password_sign_in(invitee_email, password).json()["idToken"]
        issued = exchange(token)
        check(
            "initial password reusable before expiry",
            (
                issued.status_code == 200
                and exchange(repeated).status_code == 200
                and direct(token).status_code == 200
            ),
        )
        user_cookie = issued.cookies[COOKIE]

        google_id = f"google-{run_id}"
        linked = oauth("google.com", google_id, link_token=token)
        check("emulated Google credential linked with different email", linked.status_code == 200)
        proof = oauth("google.com", google_id).json()
        check("emulated OAuth keeps UID", proof["localId"] == identity.uid)
        check(
            "Firebase-only linking cannot gain Lab OAuth admission",
            exchange(proof["idToken"]).status_code == 403,
        )
        recorded = http.post(
            f"{SITE}/lab/session/link",
            headers={
                "Origin": SITE,
                "Cookie": f"{COOKIE}={user_cookie}",
            },
            json={"provider": "google.com", "idToken": proof["idToken"]},
        )
        check(
            "fresh admitted session plus provider proof authorizes link",
            recorded.status_code == 200,
            status=recorded.status_code,
        )

        user_ref.update({"initial_password_expires_at_ms": int(time.time() * 1000) - 1})
        expired = password_sign_in(invitee_email, password)
        check("Firebase still authenticates initial password", expired.status_code == 200)
        check(
            "expired password and existing session denied on both hosts",
            (
                exchange(expired.json()["idToken"]).status_code == 403
                and browser_session(user_cookie).status_code == 403
                and direct(token).status_code == 403
            ),
        )
        allowed_oauth = exchange(proof["idToken"])
        check(
            "confirmed Google binding survives initial password expiry",
            (allowed_oauth.status_code == 200 and direct(proof["idToken"]).status_code == 200),
            status=allowed_oauth.status_code,
        )
        github_id = f"github-{run_id}"
        check(
            "emulated direct Firebase link with expired initial password",
            (
                oauth("github.com", github_id, link_token=expired.json()["idToken"]).status_code
                == 200
            ),
        )
        github_token = oauth("github.com", github_id).json()["idToken"]
        check(
            "new provider fails to bypass expiry on both hosts",
            (exchange(github_token).status_code == 403 and direct(github_token).status_code == 403),
        )
        rejected = http.post(
            f"{SITE}/lab/session/link",
            headers={
                "Origin": SITE,
                "Cookie": f"{COOKIE}={user_cookie}",
            },
            json={"provider": "github.com", "idToken": github_token},
        )
        check("expired admitted cookie cannot confirm bypass", rejected.status_code == 403)
        collision = oauth("google.com", google_id, link_token=unknown_token)
        check("credential already linked to another UID rejected", collision.status_code == 400)

        setup_email = f"setup-{run_id}@example.test"
        setup_uid, initial_code = make_link(setup_email, create=True)
        _, current_code = make_link(setup_email)
        check(
            "only latest Owner link is accepted",
            redeem(setup_uid, initial_code, replacement).status_code == 400,
        )
        check(
            "reset code cannot be presented for another UID",
            redeem(identity.uid, current_code, replacement).status_code == 400,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda _: redeem(setup_uid, current_code, replacement).status_code, range(2)
                )
            )
        check("one of two concurrent resets commits", sorted(results) == [200, 400])
        check(
            "reset replay denied and user_set written",
            (
                redeem(setup_uid, current_code, replacement).status_code == 400
                and identities.document(setup_uid).get().to_dict()["password_state"] == "user_set"
            ),
        )
        wait_past(identities.document(setup_uid).get().to_dict()["password_changed_at_ms"] // 1000)
        check(
            "new password establishes an admitted session",
            (
                exchange(password_sign_in(setup_email, replacement).json()["idToken"]).status_code
                == 200
            ),
        )

        oauth_cookie = allowed_oauth.cookies[COOKIE]
        user_ref.update(
            {
                "password_state": "reset_pending",
                "password_reset_operation_id": "emulator-interruption",
                "password_reset_started_at_ms": int(time.time() * 1000),
            }
        )
        check(
            "interrupted reset remains closed for password and admits confirmed OAuth",
            (direct(token).status_code == 403 and browser_session(oauth_cookie).status_code == 200),
        )
        wait_past(claims(proof["idToken"])["auth_time"])
        check(
            "Owner repair CLI completes",
            repair_lab_password_reset.main(
                [
                    "--uid",
                    identity.uid,
                    "--project-id",
                    PROJECT,
                    "--apply",
                ]
            )
            == 0,
        )
        check(
            "repair revokes old session and leaves password unavailable",
            (
                user_ref.get().to_dict()["password_state"] == "none"
                and browser_session(oauth_cookie).status_code in (401, 403)
            ),
        )
        _, repair_code = make_link(invitee_email)
        check(
            "fresh reset after repair is usable",
            redeem(identity.uid, repair_code, replacement).status_code == 200,
        )
        auth.update_user(OWNER, disabled=True, app=app)
        check(
            "disabled Auth user invalidates still-present session and bearer",
            (
                browser_session(owner_cookie).status_code == 401
                and direct(owner_token).status_code == 401
            ),
        )
        auth.update_user(OWNER, disabled=False, app=app)

        firestore_host = os.environ["FIRESTORE_EMULATOR_HOST"]
        document_url = (
            f"http://{firestore_host}/v1/projects/{PROJECT}/databases/(default)"
            f"/documents/portfolio_lab_identities/{identity.uid}"
        )
        check(
            "Firestore rules deny anonymous and authenticated client reads",
            (
                http.get(document_url).status_code == 403
                and http.get(
                    document_url, headers={"Authorization": f"Bearer {unknown_token}"}
                ).status_code
                == 403
            ),
        )
        check(
            "Firestore rules deny authenticated client writes",
            http.patch(
                document_url,
                headers={"Authorization": f"Bearer {unknown_token}"},
                json={"fields": {"status": {"stringValue": "active"}}},
            ).status_code
            == 403,
        )


if __name__ == "__main__":
    try:
        run()
    except SmokeFailure as failure:
        print(f"FAIL {failure}", file=sys.stderr)
        sys.exit(1)
    except Exception as failure:
        print(f"FAIL integration transport ({type(failure).__name__})", file=sys.stderr)
        sys.exit(1)
