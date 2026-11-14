"use client";

import { getApp, getApps, initializeApp } from "firebase/app";
import {
  browserPopupRedirectResolver,
  connectAuthEmulator,
  inMemoryPersistence,
  initializeAuth,
  signOut,
  type Auth,
  type User,
} from "firebase/auth";
import { LAB_RECENT_LOGIN_SECONDS } from "./session-policy";

let credentialTimer: ReturnType<typeof setTimeout> | undefined;

export function retainLabLinkCredential(auth: Auth, user: User, authTime: number): void {
  clearTimeout(credentialTimer);
  const remaining = Math.max(0, (authTime + LAB_RECENT_LOGIN_SECONDS) * 1000 - Date.now());
  credentialTimer = setTimeout(() => {
    if (auth.currentUser === user) void signOut(auth).catch(() => undefined);
  }, Math.min(remaining, LAB_RECENT_LOGIN_SECONDS * 1000));
}

/** Public client configuration only. Never put service-account secrets here. */
export function getLabAuth(): Auth {
  const config = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };
  if (Object.values(config).some((value) => !value)) {
    throw new Error("Firebase client configuration is incomplete");
  }
  const app = getApps().some((item) => item.name === "portfolio-lab")
    ? getApp("portfolio-lab")
    : initializeApp(config, "portfolio-lab");
  // The HttpOnly cookie carries the website session. Keep the client SDK
  // credential in this page's memory for the short provider-linking window.
  const auth = initializeAuth(app, {
    persistence: inMemoryPersistence,
    popupRedirectResolver: browserPopupRedirectResolver,
  });
  const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL;
  if (emulator && !auth.emulatorConfig) {
    if (!config.projectId?.startsWith("demo-") || !/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(emulator)) {
      throw new Error("Auth emulator requires a local demo project");
    }
    connectAuthEmulator(auth, emulator);
  }
  return auth;
}
