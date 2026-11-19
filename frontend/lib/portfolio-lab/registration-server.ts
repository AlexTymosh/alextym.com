import "server-only";

import type { DecodedIdToken } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid } from "./firebase-server";
import { getLabIdentityDocument } from "./lab-admission-server";
import { newLabIdentity } from "./registration-policy";
import { isRecentLabLogin } from "./session-policy";

export async function registerLabIdentity(claims: DecodedIdToken): Promise<void> {
  if (!isRecentLabLogin(claims.auth_time) || !claims.uid || claims.uid.includes("/")) return;
  // The pinned Owner must bootstrap additional providers from a password session.
  if (claims.uid === getOwnerUid()) return;

  const auth = await getLabAdminAuth();
  const identity = getLabIdentityDocument(claims.uid, auth.app);
  if ((await identity.get()).exists) return;
  const user = await auth.getUser(claims.uid);
  const record = newLabIdentity(claims, user, Date.now());
  if (!record) return;

  const db = getFirestore(auth.app);
  const event = db.collection("portfolio_lab_invitation_events").doc();
  await db.runTransaction(async (transaction) => {
    if ((await transaction.get(identity)).exists) return;
    transaction.create(identity, record);
    transaction.create(event, {
      schema_version: 1,
      uid: claims.uid,
      action: "self_registered",
      created_at_ms: record.registered_at_ms,
    });
  });
}
