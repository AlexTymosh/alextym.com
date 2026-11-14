"use client";

import { useState, type FormEvent } from "react";
import { FirebaseError } from "firebase/app";
import { useRouter } from "next/navigation";
import {
  browserSessionPersistence,
  GithubAuthProvider,
  GoogleAuthProvider,
  OAuthProvider,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  type User,
} from "firebase/auth";
import { getLabAuth } from "../lib/portfolio-lab/firebase-client";

const provider = (kind: "google" | "microsoft" | "github") => {
  if (kind === "google") return new GoogleAuthProvider();
  if (kind === "github") return new GithubAuthProvider();
  return new OAuthProvider("microsoft.com");
};

export function LabLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const finish = async (user: User) => {
    const response = await fetch("/lab/session", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken: await user.getIdToken() }),
    });
    if (!response.ok) throw new Error("Access has not been granted or session could not be created");
    router.replace("/lab");
    router.refresh();
  };
  const run = async (action: () => Promise<User>) => {
    setBusy(true); setError(""); setNotice("");
    try {
      const auth = getLabAuth();
      await setPersistence(auth, browserSessionPersistence);
      const user = await action();
      try {
        await finish(user);
      } catch (error) {
        await signOut(auth).catch(() => undefined);
        throw error;
      }
    } catch (error) {
      setError(error instanceof FirebaseError && error.code === "auth/account-exists-with-different-credential"
        ? "Sign in with your established method, then link the new provider from Portfolio Lab."
        : "Sign-in failed. Check your account or contact the Owner for access.");
    } finally { setBusy(false); }
  };
  const emailSignIn = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void run(async () => (await signInWithEmailAndPassword(getLabAuth(), email, password)).user);
  };
  const showRecoveryNotice = () => {
    setError("");
    setNotice("Request a private password setup or reset link from the Owner.");
  };

  return (
    <section style={{ maxWidth: 440, margin: "3rem auto", padding: "1rem" }}>
      <h1>Portfolio Lab sign in</h1>
      <p>Private preview. An account does not automatically grant access.</p>
      <form onSubmit={emailSignIn}>
        <label htmlFor="lab-email">Email</label>
        <input id="lab-email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ display: "block", width: "100%", marginBottom: 12 }} />
        <label htmlFor="lab-password">Password</label>
        <input id="lab-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ display: "block", width: "100%", marginBottom: 12 }} />
        <button disabled={busy} type="submit">Sign in with email</button>
      </form>
      <button type="button" disabled={busy} onClick={showRecoveryNotice}>Password help</button>
      <hr />
      {(["google", "microsoft", "github"] as const).map((kind) => (
        <p key={kind}><button type="button" disabled={busy} onClick={() => void run(async () => (await signInWithPopup(getLabAuth(), provider(kind))).user)}>Continue with {kind}</button></p>
      ))}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
