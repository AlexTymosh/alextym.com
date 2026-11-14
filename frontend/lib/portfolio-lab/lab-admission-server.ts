import "server-only";

import type { App } from "firebase-admin/app";
import type { DecodedIdToken, UserRecord } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid } from "./firebase-server";
import {
  isLabOAuthProvider,
  labAdmissionDecision,
  labOAuthSubject,
  labSignInProvider,
} from "./admission-policy";

export function getLabIdentityDocument(uid: string, app: App) {
  return getFirestore(app).collection("portfolio_lab_identities").doc(uid);
}

export function decideLabAdmission(claims: DecodedIdToken, ownerUid: string, record: unknown) {
  const provider = labSignInProvider(claims);
  return labAdmissionDecision(
    claims.uid,
    ownerUid,
    provider,
    record,
    Date.now(),
    claims.auth_time,
    isLabOAuthProvider(provider) ? labOAuthSubject(claims, provider) : undefined,
  );
}

export function hasCurrentLabOAuthSubject(
  claims: DecodedIdToken, provider: string, user: UserRecord,
): boolean {
  if (!isLabOAuthProvider(provider)) return false;
  const subject = labOAuthSubject(claims, provider);
  return Boolean(subject && !user.disabled && user.providerData.some((item) =>
    item.providerId === provider && item.uid === subject,
  ));
}

/**
 * Durable, uncached UID admission. Firebase Auth identity alone never admits a user.
 * Firestore errors are deliberately propagated; callers must fail closed.
 */
export async function getLabAdmissionDecision(claims: DecodedIdToken) {
  const ownerUid = getOwnerUid();
  if (!ownerUid || !claims.uid || claims.uid.includes("/")) return "denied" as const;
  const provider = labSignInProvider(claims);
  if (provider !== "password" && !isLabOAuthProvider(provider)) return "denied" as const;
  if (claims.uid === ownerUid && provider === "password") return "allowed" as const;
  const auth = await getLabAdminAuth();
  const document = await getLabIdentityDocument(claims.uid, auth.app).get();
  const decision = decideLabAdmission(claims, ownerUid, document.data());
  if (decision !== "allowed" || provider === "password") return decision;
  try {
    const user = await auth.getUser(claims.uid);
    return hasCurrentLabOAuthSubject(claims, provider, user) ? "allowed" : "denied";
  } catch (error) {
    if ((error as { code?: string }).code === "auth/user-not-found") return "denied";
    throw error;
  }
}
