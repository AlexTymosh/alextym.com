import "server-only";

import { FieldPath, getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid } from "./firebase-server";
import { labProjects } from "./project-catalog";
import { projectGrantRole } from "./project-grants";
import type { GrantChange } from "./grant-change";
import { isLabOAuthProvider, labOAuthBindings } from "./admission-policy";
import { labProviderNames } from "./auth-ui";

function grantRef(db: ReturnType<typeof getFirestore>, projectId: string, uid: string) {
  return db.collection("portfolio_lab_projects").doc(projectId).collection("grants").doc(uid);
}

export async function listLabUsers(after?: string) {
  const auth = await getLabAdminAuth();
  const db = getFirestore(auth.app);
  let query = db.collection("portfolio_lab_identities").orderBy(FieldPath.documentId()).limit(26);
  if (after) query = query.startAfter(after);
  const records = await query.get();
  const identities = records.docs.slice(0, 25);
  if (identities.length === 0) return { users: [], next: null };
  const accounts = await auth.getUsers(identities.map((identity) => ({ uid: identity.id })));
  const recordsByUid = new Map(identities.map((identity) => [identity.id, identity.data()]));
  const users = await Promise.all(accounts.users.map(async (account) => {
    const grants = await Promise.all(labProjects.map(async (project) => {
      const record = (await grantRef(db, project.id, account.uid).get()).data();
      return {
        projectId: project.id,
        role: projectGrantRole(account.uid, project.id, record, Date.now()) ?? "No Access",
        revision: record?.revision ?? 0,
      };
    }));
    const bindings = labOAuthBindings(recordsByUid.get(account.uid) ?? {});
    const linkedAccounts = account.providerData.filter((provider) =>
      provider.providerId === "password" || isLabOAuthProvider(provider.providerId) &&
        bindings[provider.providerId] === provider.uid,
    ).map((provider) => ({
      provider: provider.providerId,
      name: isLabOAuthProvider(provider.providerId) ? labProviderNames[provider.providerId] : "Email & password",
      email: provider.email ?? null,
    }));
    return { uid: account.uid, email: account.email ?? null, disabled: account.disabled, linkedAccounts, grants };
  }));
  return { users, next: records.size > 25 ? identities[identities.length - 1].id : null };
}

export async function changeLabGrant(change: GrantChange, actorUid: string): Promise<{ status: number; revision?: number }> {
  if (actorUid !== getOwnerUid() || change.uid === actorUid) return { status: 403 };
  const auth = await getLabAdminAuth();
  const account = await auth.getUser(change.uid);
  if (account.disabled) return { status: 409 };
  const db = getFirestore(auth.app);
  const identity = db.collection("portfolio_lab_identities").doc(change.uid);
  const grant = grantRef(db, change.projectId, change.uid);
  const event = db.collection("portfolio_lab_grant_events").doc();
  return db.runTransaction(async (transaction) => {
    const [identityRecord, grantRecord] = await transaction.getAll(identity, grant);
    const user = identityRecord.data();
    const previous = grantRecord.data();
    if (user?.schema_version !== 1 || user.uid !== change.uid || user.status !== "active") return { status: 409 };
    if ((previous?.revision ?? 0) !== change.revision) return { status: 409 };
    const revision = change.revision + 1;
    const now = Date.now();
    const record: Record<string, unknown> = {
      schema_version: 1, uid: change.uid, project_id: change.projectId,
      status: change.role === "No Access" ? "revoked" : "active",
      role: change.role === "No Access" ? "View" : change.role,
      revision, updated_at_ms: now,
    };
    if (typeof previous?.expires_at_ms === "number" && previous.expires_at_ms > now) {
      record.expires_at_ms = previous.expires_at_ms;
    }
    transaction.set(grant, record);
    transaction.create(event, {
      schema_version: 1, uid: change.uid, project_id: change.projectId,
      actor_uid: actorUid, action: "project_grant_updated",
      role: change.role, revision, created_at_ms: now,
    });
    return { status: 200, revision };
  });
}
