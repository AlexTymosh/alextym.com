"use client";

import { useState, type FormEvent } from "react";
import { EmailAuthProvider, reauthenticateWithCredential, reauthenticateWithPopup,
  signInWithEmailAndPassword, signInWithPopup, signOut } from "firebase/auth";
import type { LabOAuthProvider } from "../lib/portfolio-lab/admission-policy";
import { createLabOAuthProvider, getLabAuth } from "../lib/portfolio-lab/firebase-client";
import { labProviderNames } from "../lib/portfolio-lab/auth-ui";
import { PasswordInput } from "./password-input";
import { ProviderIcon } from "./provider-icon";
import styles from "./lab-auth.module.css";

export function AccountReauthentication({ uid, email, providers, passwordEnabled, onVerified, onCancel }: {
  uid: string; email: string; providers: LabOAuthProvider[]; passwordEnabled: boolean;
  onVerified: (authTime: number) => void; onCancel: () => void;
}) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function confirm(method: "password" | LabOAuthProvider) {
    setBusy(true); setError("");
    try {
      const auth = getLabAuth();
      const current = auth.currentUser?.uid === uid ? auth.currentUser : null;
      const proof = method === "password"
        ? current
          ? await reauthenticateWithCredential(current, EmailAuthProvider.credential(email, password))
          : await signInWithEmailAndPassword(auth, email, password)
        : current
          ? await reauthenticateWithPopup(current, createLabOAuthProvider(method))
          : await signInWithPopup(auth, createLabOAuthProvider(method));
      if (proof.user.uid !== uid) {
        await signOut(auth);
        setError("Choose an account already linked to your current account.");
        return;
      }
      const response = await fetch("/auth/session/reauthenticate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken: await proof.user.getIdToken(true) }),
      });
      if (!response.ok) throw new Error("Verification failed");
      const result = await response.json();
      onVerified(result.authTime);
    } catch {
      setError("Could not confirm your identity. Use an existing sign-in method and try again.");
    } finally { setPassword(""); setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void confirm("password"); }
  return <section className={styles.userCard} aria-labelledby="reauthentication-title">
    <h3 id="reauthentication-title">Confirm your identity</h3>
    <p className={styles.hint}>Use an existing sign-in method to continue linking. Your website session stays open.</p>
    <p className={styles.accountId}>{email}</p>
    {passwordEnabled && <form className={styles.form} onSubmit={submit}>
      <div className={styles.field}><label htmlFor="confirmation-password">Password</label>
        <PasswordInput id="confirmation-password" autoComplete="current-password" required
          value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
      </div>
      <button className={styles.primaryButton} type="submit" disabled={busy}>Confirm identity</button>
    </form>}
    {providers.map((provider) => <button key={provider} type="button" className={styles.providerButton}
      disabled={busy} onClick={() => void confirm(provider)}>
      <ProviderIcon provider={provider} />Confirm with {labProviderNames[provider]}
    </button>)}
    {error && <p role="alert" className={styles.notice}>{error}</p>}
    <button type="button" className={styles.textAction} disabled={busy} onClick={onCancel}>Cancel</button>
  </section>;
}
