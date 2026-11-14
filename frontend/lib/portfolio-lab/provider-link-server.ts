import "server-only";

import type { DecodedIdToken } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
import {
  labOAuthBindings,
  labOAuthSubject,
  labSignInProvider,
  type LabOAuthProvider,
} from "./admission-policy";
import { getLabAdminAuth } from "./firebase-server";
import {
  decideLabAdmission, getLabIdentityDocument, hasCurrentLabOAuthSubject,
} from "./lab-admission-server";
import { isRecentLabLogin } from "./session-policy";

export function linkProofSubject(
  session: DecodedIdToken,
  proof: DecodedIdToken,
  provider: LabOAuthProvider,
): string | undefined {
  if (proof.uid !== session.uid || labSignInProvider(proof) !== provider ||
      !isRecentLabLogin(session.auth_time) || !isRecentLabLogin(proof.auth_time) ||
      proof.auth_time < session.auth_time) return;
  return labOAuthSubject(proof, provider);
}

export async function confirmLabProviderLink(
  session: DecodedIdToken,
  proof: DecodedIdToken,
  provider: LabOAuthProvider,
  ownerUid: string,
): Promise<boolean> {
  const subject = linkProofSubject(session, proof, provider);
  if (!subject) return false;

  const auth = getLabAdminAuth();
  const user = await auth.getUser(session.uid);
  if (!hasCurrentLabOAuthSubject(proof, provider, user)) return false;
  const currentProvider = labSignInProvider(session);
  if (currentProvider !== "password" && !hasCurrentLabOAuthSubject(session, currentProvider, user)) {
    return false;
  }

  const db = getFirestore(auth.app);
  const identity = getLabIdentityDocument(session.uid);
  const event = db.collection("portfolio_lab_invitation_events").doc();
  return db.runTransaction(async (transaction) => {
    const record = (await transaction.get(identity)).data();
    if (!isRecentLabLogin(session.auth_time) || !isRecentLabLogin(proof.auth_time) ||
        decideLabAdmission(session, ownerUid, record) !== "allowed") return false;
    if (record && record.status !== "active") return false;

    const bindings = labOAuthBindings(record ?? {});
    if (bindings[provider] === subject) return true;
    if (bindings[provider]) return false;
    bindings[provider] = subject;
    if (record) {
      transaction.update(identity, { oauth_provider_subjects: bindings });
    } else {
      // The pinned Owner may bootstrap from a password session.
      transaction.create(identity, {
        schema_version: 1,
        uid: session.uid,
        status: "active",
        password_state: "user_set",
        oauth_provider_subjects: bindings,
      });
    }
    transaction.create(event, {
      schema_version: 1,
      uid: session.uid,
      provider,
      action: "oauth_provider_linked",
      created_at_ms: Date.now(),
    });
    return true;
  });
}
