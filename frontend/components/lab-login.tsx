"use client";

import { useState, type FormEvent } from "react";
import { FirebaseError } from "firebase/app";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword, signInWithPopup, signOut, type Auth, type User } from "firebase/auth";
import type { LabOAuthProvider } from "../lib/portfolio-lab/admission-policy";
import { labOAuthIssue, labProviderNames, labSignInProviders } from "../lib/portfolio-lab/auth-ui";
import { createLabOAuthProvider, getLabAuth, retainLabLinkCredential } from "../lib/portfolio-lab/firebase-client";
import { ProviderIcon } from "./provider-icon";
import styles from "./lab-auth.module.css";

type SignInMethod = "password" | LabOAuthProvider;

function linkingInstructions(provider: LabOAuthProvider) {
  return `Sign in with your invitation email and password, then choose Link ${labProviderNames[provider]} under Linked identities.`;
}

async function startLabSession(auth: Auth, user: User, method: SignInMethod): Promise<string | null> {
  const token = await user.getIdTokenResult();
  const response = await fetch("/lab/session", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken: token.token }),
  });
  if (response.ok) {
    retainLabLinkCredential(auth, user, Date.parse(token.authTime) / 1000);
    return null;
  }

  const body = await response.json().catch(() => null);
  if (response.status === 403 && body?.code === "PASSWORD_EXPIRED") {
    return "Your initial password has expired. Ask the Owner for a new password setup link.";
  }
  if (response.status === 403 && body?.code === "ACCESS_DENIED") {
    return method === "password"
      ? "Portfolio Lab access has not been granted. Contact the Owner for help with your invitation."
      : `Portfolio Lab could not grant access to this ${labProviderNames[method]} account. ${linkingInstructions(method)}`;
  }
  if (response.status >= 500) {
    return "Portfolio Lab sign-in is temporarily unavailable. Try again shortly.";
  }
  return "Portfolio Lab could not start a session. Try signing in again.";
}

function signInIssue(error: unknown, method: SignInMethod) {
  const code = error instanceof FirebaseError ? error.code : undefined;
  if (method === "password") {
    if (code === "auth/network-request-failed" || code === undefined) {
      return "Sign-in is temporarily unavailable. Try again shortly.";
    }
    return "Sign-in failed. Check your email and password or ask the Owner for a setup link.";
  }
  if (code === "auth/account-exists-with-different-credential" || code === "auth/credential-already-in-use") {
    return linkingInstructions(method);
  }
  return labOAuthIssue(method, code)
    ?? `Could not sign in with ${labProviderNames[method]}. Try again or sign in with email.`;
}

export function LabLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState<SignInMethod | null>(null);
  const [message, setMessage] = useState<{ tone: "error" | "info"; text: string } | null>(null);
  const busy = pending !== null;

  const signIn = async (method: SignInMethod) => {
    setPending(method);
    setMessage(null);
    try {
      const auth = getLabAuth();
      const { user } = method === "password"
        ? await signInWithEmailAndPassword(auth, email, password)
        : await signInWithPopup(auth, createLabOAuthProvider(method));
      const issue = await startLabSession(auth, user, method)
        .catch(() => "Could not reach Portfolio Lab. Try signing in again.");
      if (issue) {
        await signOut(auth).catch(() => undefined);
        setMessage({ tone: "error", text: issue });
        return;
      }
      router.replace("/lab");
      router.refresh();
    } catch (error) {
      setMessage({ tone: "error", text: signInIssue(error, method) });
    } finally {
      setPending(null);
    }
  };

  const emailSignIn = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void signIn("password");
  };

  return (
    <section className={styles.panel} aria-labelledby="lab-login-title">
      <header className={styles.header}>
        <h1 id="lab-login-title">Portfolio Lab sign in</h1>
        <p>For your first visit, use the email and password from your invitation. You can link another account after signing in.</p>
      </header>

      {message && (
        <p
          className={`${styles.notice} ${message.tone === "error" ? styles.error : ""}`}
          role={message.tone === "error" ? "alert" : "status"}
        >
          {message.text}
        </p>
      )}

      <div className={styles.stack} role="group" aria-label="Sign in with a linked account">
        {labSignInProviders.map((provider) => (
          <button
            key={provider}
            type="button"
            className={styles.providerButton}
            disabled={busy}
            onClick={() => void signIn(provider)}
          >
            <ProviderIcon provider={provider} />
            <span>{pending === provider ? `Signing in with ${labProviderNames[provider]}…` : `Continue with ${labProviderNames[provider]}`}</span>
          </button>
        ))}
      </div>

      <p className={styles.divider}>or sign in with email</p>
      <form className={styles.form} onSubmit={emailSignIn}>
        <div className={styles.field}>
          <label htmlFor="lab-email">Email</label>
          <input
            id="lab-email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="lab-password">Password</label>
          <input
            id="lab-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
        <button type="submit" className={styles.primaryButton} disabled={busy}>
          {pending === "password" ? "Signing in…" : "Sign in with email"}
        </button>
        <button
          type="button"
          className={styles.textAction}
          disabled={busy}
          onClick={() => setMessage({ tone: "info", text: "Ask the Owner for a private password setup or reset link." })}
        >
          Password help
        </button>
      </form>
    </section>
  );
}
