"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  GithubAuthProvider,
  GoogleAuthProvider,
  OAuthProvider,
  linkWithPopup,
  reauthenticateWithPopup,
  signOut,
} from "firebase/auth";
import { LAB_RECENT_LOGIN_SECONDS } from "../lib/portfolio-lab/session-policy";
import { getLabAuth } from "../lib/portfolio-lab/firebase-client";

const kinds = ["google", "microsoft", "github"] as const;
type ProviderKind = (typeof kinds)[number];

function oauthProvider(kind: ProviderKind) {
  if (kind === "google") return new GoogleAuthProvider();
  if (kind === "github") return new GithubAuthProvider();
  return new OAuthProvider("microsoft.com");
}

export function LabAccountActions() {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ kind: ProviderKind; step: "link" | "confirm" } | null>(null);
  const prepare = async (kind: ProviderKind) => {
    setBusy(true); setMessage("");
    setPending(null);
    try {
      const auth = getLabAuth();
      await auth.authStateReady();
      const user = auth.currentUser;
      const session = await fetch("/lab/session", { credentials: "same-origin", cache: "no-store" });
      const status = session.ok ? await session.json() : null;
      if (!user || status?.canLink !== true) {
        setMessage(`Sign in again to link a provider within ${LAB_RECENT_LOGIN_SECONDS / 60} minutes.`);
        return;
      }
      const provider = oauthProvider(kind);
      const alreadyLinked = user.providerData.some((item) => item.providerId === provider.providerId);
      setPending({ kind, step: alreadyLinked ? "confirm" : "link" });
      setMessage(alreadyLinked ? "Confirm the provider to finish linking." : "Open the provider to sign in.");
    } catch {
      setMessage("Could not check your session. Sign in again before linking.");
    } finally { setBusy(false); }
  };

  const confirm = async (kind: ProviderKind) => {
    setBusy(true);
    setMessage("");
    try {
      const user = getLabAuth().currentUser;
      if (!user) throw new Error("Sign in again before linking");
      const provider = oauthProvider(kind);
      if (pending?.step === "link") {
        await linkWithPopup(user, provider);
        setPending({ kind, step: "confirm" });
        setMessage("Confirm the provider to finish linking.");
        return;
      }
      const proof = await reauthenticateWithPopup(user, provider);
      const response = await fetch("/lab/session/link", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: provider.providerId, idToken: await proof.user.getIdToken() }),
      });
      if (!response.ok) throw new Error("Provider proof was not accepted");
      setPending(null);
      setMessage("Provider linked to the existing account.");
    } catch {
      setMessage("Linking could not be confirmed. Sign in with your established method and try again. Contact the Owner if the provider belongs to another account.");
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
      <p>Link a provider within five minutes of signing in.</p>
      {kinds.map((kind) => (
        <p key={kind}>
          {pending?.kind === kind
            ? <button disabled={busy} onClick={() => void confirm(kind)}>
                {pending.step === "link" ? "Open" : "Confirm"} {kind}
              </button>
            : <button disabled={busy} onClick={() => void prepare(kind)}>Link {kind}</button>}
        </p>
      ))}
      <p><button disabled={busy} onClick={() => void logout()}>Sign out</button></p>
      {message && <p role="status">{message}</p>}
    </div>
  );
}
