import "server-only";

import { getFirestore } from "firebase-admin/firestore";
import { getLabAdmissionDecision } from "./lab-admission-server";
import { getLabAdminAuth, getOwnerUid, isLabEnabled } from "./firebase-server";
import { adminGrantAllows, WORKFORCE_PROJECT_ID } from "./project-grants";

export type WorkforceAccess =
  | { kind: "disabled" | "unauthenticated" | "denied" | "unavailable" }
  | { kind: "allowed"; uid: string };

export function isWorkforceEnabled(): boolean {
  return isLabEnabled() && process.env.WORKFORCE_INTELLIGENCE_ENABLED === "true";
}

/** Checks a signed, revocation-checked session and current Firestore grant. */
export async function getWorkforceAccess(sessionCookie?: string): Promise<WorkforceAccess> {
  if (!isWorkforceEnabled()) return { kind: "disabled" };
  const ownerUid = getOwnerUid();
  if (!ownerUid) return { kind: "unavailable" };
  if (!sessionCookie) return { kind: "unauthenticated" };

  let auth;
  try {
    auth = await getLabAdminAuth();
  } catch {
    return { kind: "unavailable" };
  }
  let claims;
  try {
    claims = await auth.verifySessionCookie(sessionCookie, true);
  } catch {
    return { kind: "unauthenticated" };
  }
  if (!claims.uid || claims.uid.includes("/")) return { kind: "denied" };
  try {
    if (await getLabAdmissionDecision(claims) !== "allowed") return { kind: "denied" };
    if (claims.uid === ownerUid) return { kind: "allowed", uid: claims.uid };
    const snapshot = await getFirestore(auth.app)
      .collection("portfolio_lab_projects")
      .doc(WORKFORCE_PROJECT_ID)
      .collection("grants")
      .doc(claims.uid)
      .get();
    return adminGrantAllows(
      claims.uid, WORKFORCE_PROJECT_ID, snapshot.exists ? snapshot.data() : null, Date.now(),
    ) ? { kind: "allowed", uid: claims.uid } : { kind: "denied" };
  } catch {
    // Firestore and admission outages must never become an implicit grant.
    return { kind: "unavailable" };
  }
}
