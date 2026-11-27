"use client";
// Host adapter supplies existing Firebase identity; the project owns every screen.
import { useSyncExternalStore } from "react";
import { SamePlaceRoomCore, InvalidRoomInvitation, validInviteToken, type Authenticate } from "@sameplace";
import { getLabAuth, createLabOAuthProvider } from "../../../lib/portfolio-lab/firebase-client";
import { createUserWithEmailAndPassword, sendEmailVerification, signInWithEmailAndPassword, signInWithPopup, signOut } from "firebase/auth";

const api = "/portfolio/sameplace/api";
const authenticate: Authenticate = async (mode, email, password) => {
  const auth = getLabAuth();
  try {
    const result = mode === "google" ? await signInWithPopup(auth, createLabOAuthProvider("google.com"))
      : mode === "register" ? await createUserWithEmailAndPassword(auth, email, password)
      : await signInWithEmailAndPassword(auth, email, password);
    if (mode === "register") {
      await sendEmailVerification(result.user);
      return "verify-email";
    }
    const idToken = await result.user.getIdToken(true);
    const response = await fetch(`${api}/session`, { method: "POST", credentials: "same-origin", cache: "no-store", referrerPolicy: "no-referrer", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ idToken }) });
    if (!response.ok) throw new Error("SamePlace sign-in failed");
    return "signed-in";
  } finally {
    // The credential is carried in a scoped HttpOnly cookie, not browser storage.
    await signOut(auth).catch(() => undefined);
  }
};
async function logout() {
  const response = await fetch(`${api}/signout`, { method: "POST", credentials: "same-origin", cache: "no-store", referrerPolicy: "no-referrer", headers: { "Content-Type": "application/json" }, body: "{}" });
  if (!response.ok) throw new Error("SamePlace sign-out failed");
}
export function SamePlaceClient({ slug, token }: { slug?: string; token?: string }) {
  return <SamePlaceRoomCore key={slug ?? token ?? "catalogue"} slug={slug} token={token} authenticate={authenticate} signOut={logout} />;
}

function subscribeHash(callback: () => void) { window.addEventListener("hashchange", callback); return () => window.removeEventListener("hashchange", callback); }
function currentHash() { return window.location.hash.slice(1); }
function serverHash(): string | null { return null; }
export function SamePlaceInvitationClient() {
  const token = useSyncExternalStore(subscribeHash, currentHash, serverHash);
  if (token === null) return <InvalidRoomInvitation loading />;
  if (!validInviteToken(token)) return <InvalidRoomInvitation />;
  return <SamePlaceClient token={token} />;
}
