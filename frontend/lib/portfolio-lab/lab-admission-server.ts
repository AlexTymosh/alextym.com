import "server-only";

import type { DecodedIdToken } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid } from "./firebase-server";
import { labAdmissionDecision, labSignInProvider } from "./admission-policy";

/**
 * Durable, uncached UID admission. Firebase Auth identity alone never admits a user.
 * Firestore errors are deliberately propagated; callers must fail closed.
 */
export async function getLabAdmissionDecision(claims: DecodedIdToken) {
  const ownerUid = getOwnerUid();
  if (!ownerUid) return "denied" as const;
  if (claims.uid === ownerUid) return "allowed" as const;
  if (!claims.uid || claims.uid.includes("/")) return "denied" as const;

  const auth = getLabAdminAuth();
  const document = await getFirestore(auth.app)
    .collection("portfolio_lab_identities")
    .doc(claims.uid)
    .get();
  return labAdmissionDecision(
    claims.uid,
    ownerUid,
    labSignInProvider(claims),
    document.exists ? document.data() : null,
    Date.now(),
  );
}
