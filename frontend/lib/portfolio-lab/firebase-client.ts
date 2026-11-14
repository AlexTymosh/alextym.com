"use client";

import { getApp, getApps, initializeApp } from "firebase/app";
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth";

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
  const auth = getAuth(app);
  const emulator = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL;
  if (emulator && !auth.emulatorConfig) {
    if (!config.projectId?.startsWith("demo-") || !/^http:\/\/127\.0\.0\.1:\d{1,5}$/.test(emulator)) {
      throw new Error("Auth emulator requires a local demo project");
    }
    connectAuthEmulator(auth, emulator);
  }
  return auth;
}
