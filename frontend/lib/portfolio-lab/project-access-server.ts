import "server-only";

import type { DecodedIdToken } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getLabAdminAuth, getOwnerUid, isLabEnabled, LAB_SESSION_COOKIE } from "./firebase-server";
import { getLabAdmissionDecision } from "./lab-admission-server";
import { projectGrantRole, projectRoleAllows, type ProjectRole } from "./project-grants";
import { labProjects } from "./project-catalog";

export async function labSession(cookie?: string): Promise<DecodedIdToken | null> {
  if (!isLabEnabled() || !getOwnerUid() || !cookie) return null;
  const auth = await getLabAdminAuth();
  const claims = await auth.verifySessionCookie(cookie, true).catch(() => null);
  if (!claims) return null;
  return await getLabAdmissionDecision(claims) === "allowed" ? claims : null;
}

export async function currentLabSession() {
  return labSession((await cookies()).get(LAB_SESSION_COOKIE)?.value);
}

export async function labProjectRole(uid: string, projectId: string): Promise<ProjectRole | null> {
  if (!labProjects.some((project) => project.id === projectId)) return null;
  if (uid === getOwnerUid()) return "Admin";
  const auth = await getLabAdminAuth();
  const grant = await getFirestore(auth.app).collection("portfolio_lab_projects").doc(projectId)
    .collection("grants").doc(uid).get();
  return projectGrantRole(uid, projectId, grant.data(), Date.now());
}

export async function labProjectAccess(cookie: string | undefined, projectId: string, method: string, path: string) {
  const claims = await labSession(cookie);
  if (!claims) return { status: 401, role: null };
  const role = await labProjectRole(claims.uid, projectId);
  return { status: projectRoleAllows(role, method, path) ? 200 : 403, role };
}

export async function requireLabProjectPage(projectId: string) {
  if (!isLabEnabled()) return;
  const session = await currentLabSession().catch(() => null);
  if (!session) redirect("/sign-in");
  const role = await labProjectRole(session.uid, projectId).catch(() => null);
  if (!role) redirect("/settings");
}
