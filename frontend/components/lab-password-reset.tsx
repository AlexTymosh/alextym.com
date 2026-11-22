"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { confirmPasswordReset, verifyPasswordResetCode } from "firebase/auth";
import { ACCOUNT_PASSWORD_MIN_LENGTH, ACCOUNT_PASSWORD_MAX_LENGTH, validNewPassword, validResetCode, validResetUid } from "../lib/portfolio-lab/password-recovery-policy";
import { getLabAuth } from "../lib/portfolio-lab/firebase-client";
import { siteConfig } from "../lib/site-config";
import { PasswordInput } from "./password-input";
import styles from "./lab-auth.module.css";

type ResetLink = { uid: string | null; code: string | null; mode: string | null };

export function LabPasswordReset() {
  const [link, setLink] = useState<ResetLink | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const capturedLink = useRef<ResetLink | null>(null);

  useEffect(() => {
    if (capturedLink.current === null) {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      const query = new URLSearchParams(window.location.search);
      capturedLink.current = {
        uid: fragment.get("uid"), code: fragment.get("oobCode") || query.get("oobCode"),
        mode: query.get("mode"),
      };
      window.history.replaceState(null, "", "/auth/action");
    }

    const supplied = capturedLink.current;
    let cancelled = false;
    async function check() {
      if (!supplied || !validResetCode(supplied.code) ||
          (!validResetUid(supplied.uid) && supplied.mode !== "resetPassword")) {
        if (!cancelled) setMessage("This link is invalid. Request a new password reset email.");
        return;
      }
      try {
        if (!supplied.uid) await verifyPasswordResetCode(getLabAuth(), supplied.code);
        if (!cancelled) setLink(supplied);
      } catch {
        if (!cancelled) setMessage("This link has expired or has already been used. Request a new password reset email.");
      }
    }
    void check();
    return () => { cancelled = true; };
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!link || !validResetCode(link.code)) return;
    if (!validNewPassword(password)) {
      setMessage("Use 8–128 characters for your new password.");
      return;
    }
    if (password !== confirm) {
      setMessage("The passwords do not match. Enter the same password in both fields.");
      return;
    }
    setBusy(true); setMessage("");
    try {
      if (link.uid) {
        const response = await fetch("/auth/password/reset", {
          method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uid: link.uid, oobCode: link.code, newPassword: password }),
        });
        if (!response.ok) throw new Error("Reset did not complete");
      } else {
        // Firebase verifies and consumes its own single-use email action code.
        await confirmPasswordReset(getLabAuth(), link.code, password);
      }
      setLink(null); setPassword(""); setConfirm(""); setDone(true);
      setMessage("Password updated. You can now log in.");
    } catch {
      setMessage("The password could not be updated. Request a fresh link and try again.");
    } finally { setBusy(false); }
  };

  return (
    <section className={styles.panel} aria-labelledby="password-reset-title">
      <Link href="/" className={styles.authBrand}>
        <Image src="/icon.png" width={48} height={48} alt="" />
        <span>{siteConfig.name}</span>
      </Link>
      <header className={styles.header}>
        <h1 id="password-reset-title">{done ? "Password updated" : "Set your password"}</h1>
        {!done && <p>Choose a password with 8–128 characters.</p>}
      </header>
      {!done && link && (
        <form className={styles.form} onSubmit={(event) => void submit(event)}>
          <div className={styles.field}>
            <label htmlFor="new-password">New password</label>
            <PasswordInput id="new-password" autoComplete="new-password" required minLength={ACCOUNT_PASSWORD_MIN_LENGTH} maxLength={ACCOUNT_PASSWORD_MAX_LENGTH}
              disabled={busy} value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          <div className={styles.field}>
            <label htmlFor="confirm-password">Confirm password</label>
            <PasswordInput id="confirm-password" autoComplete="new-password" required minLength={ACCOUNT_PASSWORD_MIN_LENGTH} maxLength={ACCOUNT_PASSWORD_MAX_LENGTH}
              disabled={busy} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
          </div>
          <button className={styles.primaryButton} type="submit" disabled={busy}>{busy ? "Updating password…" : "Set password"}</button>
        </form>
      )}
      {message && <p className={styles.notice} role="status">{message}</p>}
      <Link className={done ? styles.primaryButton : styles.textAction} href="/sign-in">Back to Log In</Link>
    </section>
  );
}
