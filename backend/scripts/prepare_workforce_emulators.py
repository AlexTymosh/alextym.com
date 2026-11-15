"""Create the fictional member used by Workforce's browser smoke test."""

import os

from firebase_admin import auth, firestore

from app.security.firebase_identity import _firebase_app
from app.security.project_grants import WORKFORCE_PROJECT_ID, grant_document


def main() -> int:
    expected = {
        "FIREBASE_PROJECT_ID": "demo-portfolio-lab",
        "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:19099",
        "FIRESTORE_EMULATOR_HOST": "127.0.0.1:18080",
    }
    if (
        os.getenv("RENDER")
        or os.getenv("VERCEL")
        or any(os.getenv(key) != value for key, value in expected.items())
    ):
        raise SystemExit("This fixture requires both local demo Firebase emulators")

    app = _firebase_app()
    db = firestore.client(app=app)
    uid = "workforce-emulator-member"
    try:
        auth.get_user(uid, app=app)
    except auth.UserNotFoundError:
        auth.create_user(
            uid=uid,
            email="workforce-member@example.test",
            password="Workforce-emulator-only-091!",
            app=app,
        )
    db.collection("portfolio_lab_identities").document(uid).set(
        {
            "schema_version": 1,
            "uid": uid,
            "status": "active",
            "password_state": "user_set",
        }
    )
    grant_document(db, WORKFORCE_PROJECT_ID, uid).set(
        {
            "schema_version": 1,
            "uid": uid,
            "project_id": WORKFORCE_PROJECT_ID,
            "status": "active",
            "role": "Admin",
        }
    )
    print("Prepared the fictional Workforce member in the local emulators.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
