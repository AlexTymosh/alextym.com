import "server-only";

import { applicationDefault, cert, getApps, initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";

export const LAB_SESSION_MAX_AGE_MS = 5 * 24 * 60 * 60 * 1000;
export const LAB_SESSION_COOKIE =
  process.env.NODE_ENV === "production"
    ? "__Host-portfolio_lab_session"
    : "portfolio_lab_session";

export function isLabEnabled(): boolean {
  return process.env.PORTFOLIO_LAB_ENABLED === "true";
}

export function getOwnerUid(): string {
  return process.env.PORTFOLIO_LAB_OWNER_UID?.trim() || "";
}

/** Server only. Must never run or serialize credentials in a client component. */
export function getLabAdminAuth() {
  const projectId = process.env.FIREBASE_PROJECT_ID?.trim();
  if (!projectId) throw new Error("Missing Firebase server project ID");
  if (!getApps().length) {
    const serviceAccount = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
    const credential = serviceAccount
      ? cert(JSON.parse(serviceAccount))
      : applicationDefault();
    initializeApp({ credential, projectId });
  }
  return getAuth();
}
