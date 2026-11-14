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
  if (projectId !== process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) {
    throw new Error("Firebase browser and server projects must match");
  }
  const emulatorHosts = [process.env.FIREBASE_AUTH_EMULATOR_HOST, process.env.FIRESTORE_EMULATOR_HOST];
  if (emulatorHosts.some(Boolean) && (process.env.VERCEL || !projectId.startsWith("demo-") ||
      !emulatorHosts.every((host) => host && /^127\.0\.0\.1:\d{1,5}$/.test(host)))) {
    throw new Error("Both Firebase emulators must use a local demo project");
  }
  const existingApp = getApps().find((app) => app.name === "portfolio-lab");
  if (existingApp) {
    if (existingApp.options.projectId !== projectId) {
      throw new Error("Portfolio Lab Firebase project does not match configuration");
    }
    return getAuth(existingApp);
  }
  const rawAccount = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  const serviceAccount = rawAccount ? JSON.parse(rawAccount) : null;
  if (rawAccount && serviceAccount?.project_id !== projectId) {
    throw new Error("Firebase credential project does not match configuration");
  }
  const credential = serviceAccount ? cert(serviceAccount) : applicationDefault();
  const app = initializeApp({ credential, projectId }, "portfolio-lab");
  return getAuth(app);
}
