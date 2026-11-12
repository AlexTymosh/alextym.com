"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  GithubAuthProvider,
  GoogleAuthProvider,
  OAuthProvider,
  linkWithPopup,
  signOut,
} from "firebase/auth";
import { getLabAuth } from "../lib/portfolio-lab/firebase-client";

export function LabAccountActions() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const link = async (kind: "google" | "microsoft" | "github") => {
    setBusy(true); setMessage("");
    try {
      const auth = getLabAuth();
      const user = auth.currentUser;
      if (!user) throw new Error("Sign in again before linking another identity");
      const provider = kind === "google"
        ? new GoogleAuthProvider()
        : kind === "github" ? new GithubAuthProvider() : new OAuthProvider("microsoft.com");
      const linked = await linkWithPopup(user, provider);
      if (linked.user.uid !== user.uid) throw new Error("UID changed unexpectedly");
      setMessage("Provider linked to the existing account.");
    } catch {
      setMessage("Linking failed. Sign in again; an existing linked account cannot be merged automatically.");
    } finally { setBusy(false); }
  };
  const logout = async () => {
    setBusy(true);
    try {
      const response = await fetch("/lab/session", { method: "DELETE", credentials: "same-origin" });
      if (!response.ok) throw new Error("Logout failed");
      await signOut(getLabAuth());
      router.replace("/lab/login");
      router.refresh();
    } catch { setMessage("Unable to sign out. Retry, or clear site cookies."); }
    finally { setBusy(false); }
  };
  return (
    <div>
      <h2>Linked identities</h2>
      <p>Linking requires signing into your current account first. Different provider email addresses are supported without automatically merging Firebase users.</p>
      {(["google", "microsoft", "github"] as const).map((kind) => (
        <p key={kind}><button disabled={busy} onClick={() => void link(kind)}>Link {kind}</button></p>
      ))}
      <p><button disabled={busy} onClick={() => void logout()}>Sign out</button></p>
      {message && <p role="status">{message}</p>}
    </div>
  );
}
