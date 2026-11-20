"use client";

import { useState, type FormEvent } from "react";
import { FirebaseError } from "firebase/app";
import { useRouter } from "next/navigation";
import { createUserWithEmailAndPassword, sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup, signOut, type Auth, type User } from "firebase/auth";
import type { LabOAuthProvider } from "../lib/portfolio-lab/admission-policy";
import { labOAuthIssue, labProviderNames, labSignInProviders } from "../lib/portfolio-lab/auth-ui";
import { createLabOAuthProvider, getLabAuth, retainLabLinkCredential } from "../lib/portfolio-lab/firebase-client";
import { validNewPassword } from "../lib/portfolio-lab/password-recovery-policy";
import { ProviderIcon } from "./provider-icon";
import { PasswordInput } from "./password-input";
import { useClientReady } from "../lib/use-client-ready";
import styles from "./lab-auth.module.css";

type SignInMethod = "password" | LabOAuthProvider;

function linkingInstructions(provider: LabOAuthProvider) {
  return `Sign in with an existing method for your account, then choose Link ${labProviderNames[provider]} under Linked accounts.`;
}

async function startLabSession(auth: Auth, user: User, method: SignInMethod): Promise<string | null> {
  const token = await user.getIdTokenResult();
  const response = await fetch("/auth/session", {
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
    return "Your initial password has expired. Contact support for a new password setup link.";
  }
  if (response.status === 403 && body?.code === "ACCESS_DENIED") {
    return method === "password"
      ? "Sign-in is unavailable for this account. Contact support for help."
      : "This sign-in method is unavailable for your account. Sign in with an existing method or contact support.";
  }
  if (response.status >= 500) {
    return "Sign-in is temporarily unavailable. Try again shortly.";
  }
  return "Could not start a session. Try signing in again.";
}

function signInIssue(error: unknown, method: SignInMethod) {
  const code = error instanceof FirebaseError ? error.code : undefined;
  if (method === "password") {
    if (code === "auth/network-request-failed" || code === undefined) {
      return "Sign-in is temporarily unavailable. Try again shortly.";
    }
    return "Sign-in failed. Check your email and password or contact support for a setup link.";
  }
  if (code === "auth/account-exists-with-different-credential" || code === "auth/credential-already-in-use") {
    return linkingInstructions(method);
  }
  return labOAuthIssue(method, code)
    ?? `Could not sign in with ${labProviderNames[method]}. Try again or sign in with email.`;
}

export function LabLogin() {
  const router = useRouter();
  const ready = useClientReady();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [register, setRegister] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState<SignInMethod | "recovery" | null>(null);
  const [message, setMessage] = useState<{ tone: "error" | "info"; text: string } | null>(null);
  const busy = !ready || pending !== null;

  const signIn = async (method: SignInMethod) => {
    setPending(method);
    setMessage(null);
    try {
      const auth = getLabAuth();
      let user: User;
      if (method !== "password") {
        user = (await signInWithPopup(auth, createLabOAuthProvider(method))).user;
      } else if (register) {
        user = (await createUserWithEmailAndPassword(auth, email, password)).user;
      } else {
        user = (await signInWithEmailAndPassword(auth, email, password)).user;
      }
      const issue = await startLabSession(auth, user, method)
        .catch(() => "Could not connect. Try signing in again.");
      if (issue) {
        await signOut(auth).catch(() => undefined);
        setMessage({ tone: "error", text: issue });
        return;
      }
      router.replace("/settings");
      router.refresh();
    } catch (error) {
      const text = register && method === "password"
        ? "Could not create an account. Try signing in if you registered before, or contact support."
        : signInIssue(error, method);
      setMessage({ tone: "error", text });
    } finally {
      setPending(null);
    }
  };

  const emailSignIn = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (register && (!validNewPassword(password) || password !== confirmation)) {
      setMessage({ tone: "error", text: "Choose a password of 12–128 characters and enter it again to confirm." });
      return;
    }
    void signIn("password");
  };

  const passwordHelp = async () => {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setMessage({ tone: "info", text: "Enter your email address, then choose Password help." });
      return;
    }
    setPending("recovery");
    setMessage(null);
    try {
      await sendPasswordResetEmail(getLabAuth(), email);
      setMessage({ tone: "info", text: "If an account uses that email, a password reset link has been sent. Check your inbox." });
    } catch {
      setMessage({ tone: "error", text: "Unable to request a reset link. Try again shortly." });
    } finally {
      setPending(null);
    }
  };

  return (
    <section className={styles.panel} aria-labelledby="lab-login-title">
      <header className={styles.header}>
        <h1 id="lab-login-title">{register ? "Create your account" : "Sign in"}</h1>
      </header>

      {message && (
        <p
          className={`${styles.notice} ${message.tone === "error" ? styles.error : ""}`}
          role={message.tone === "error" ? "alert" : "status"}
        >
          {message.text}
        </p>
      )}

      <div className={styles.modeSwitch} role="group" aria-label="Account access">
        <button type="button" disabled={busy} aria-pressed={!register}
          onClick={() => { setRegister(false); setMessage(null); setConfirmation(""); }}>Sign in</button>
        <button type="button" disabled={busy} aria-pressed={register}
          onClick={() => { setRegister(true); setMessage(null); setConfirmation(""); }}>Create account</button>
      </div>
      <form className={styles.form} onSubmit={emailSignIn}>
        <div className={styles.field}>
          <label htmlFor="lab-email">Email</label>
          <input
            id="lab-email"
            type="email"
            autoComplete="username"
            value={email}
            disabled={busy}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="lab-password">Password</label>
          <PasswordInput
            id="lab-password"
            autoComplete={register ? "new-password" : "current-password"}
            minLength={register ? 12 : undefined}
            maxLength={register ? 128 : undefined}
            value={password}
            disabled={busy}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
        {register && (
          <div className={styles.field}>
            <label htmlFor="lab-password-confirm">Confirm password</label>
            <PasswordInput id="lab-password-confirm" autoComplete="new-password"
              value={confirmation} disabled={busy} onChange={(event) => setConfirmation(event.target.value)} required />
          </div>
        )}
        <button type="submit" className={styles.primaryButton} disabled={busy}>
          {pending === "password" ? "Please wait…" : register ? "Create account with email" : "Sign in with email"}
        </button>
        <button
          type="button"
          className={styles.textAction}
          disabled={busy}
          onClick={() => void passwordHelp()}
        >
          Password help
        </button>
      </form>
      <p className={styles.divider}>or continue with</p>
      <div className={styles.stack} role="group" aria-label="Continue with a provider">
        {labSignInProviders.map((provider) => (
          <button key={provider} type="button" className={styles.providerButton} disabled={busy}
            onClick={() => void signIn(provider)}>
            <ProviderIcon provider={provider} />
            <span>{pending === provider ? `Signing in with ${labProviderNames[provider]}…` : `Continue with ${labProviderNames[provider]}`}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
