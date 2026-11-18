"use client";

import { useState } from "react";
import { FirebaseError } from "firebase/app";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { linkWithPopup, reauthenticateWithPopup, signOut } from "firebase/auth";
import type { LabOAuthProvider } from "../lib/portfolio-lab/admission-policy";
import { labOAuthIssue, labProviderNames, labSignInProviders } from "../lib/portfolio-lab/auth-ui";
import { createLabOAuthProvider, getLabAuth } from "../lib/portfolio-lab/firebase-client";
import { LAB_RECENT_LOGIN_SECONDS } from "../lib/portfolio-lab/session-policy";
import { ProviderIcon } from "./provider-icon";
import styles from "./lab-auth.module.css";

type PendingLink = { provider: LabOAuthProvider; step: "open" | "confirm" };
type LinkNotice = { tone: "info" | "error" | "success"; text: string };

function confirmNotice(provider: LabOAuthProvider): LinkNotice {
  return {
    tone: "info",
    text: `Select Confirm ${labProviderNames[provider]}, then choose the same account to finish linking.`,
  };
}

function linkIssue(error: unknown, provider: LabOAuthProvider) {
  const code = error instanceof FirebaseError ? error.code : undefined;
  if (code === "auth/credential-already-in-use" || code === "auth/email-already-in-use" ||
      code === "auth/account-exists-with-different-credential") {
    return `This ${labProviderNames[provider]} account is already attached to a separate sign-in. Contact support to resolve the conflict before linking it here.`;
  }
  return labOAuthIssue(provider, code)
    ?? `Could not finish linking ${labProviderNames[provider]}. Sign in again and retry.`;
}

export function LabAccountActions({ linkedProviders }: { linkedProviders: LabOAuthProvider[] | null }) {
  const router = useRouter();
  const [notice, setNotice] = useState<LinkNotice | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingLink | null>(null);
  const [confirmed, setConfirmed] = useState<LabOAuthProvider[]>([]);

  const prepare = async (provider: LabOAuthProvider) => {
    setBusy(true);
    setNotice(null);
    setPending(null);
    try {
      const auth = getLabAuth();
      await auth.authStateReady();
      const response = await fetch("/lab/session", { credentials: "same-origin", cache: "no-store" });
      const session = response.ok ? await response.json() : null;
      if (!auth.currentUser || session?.canLink !== true) {
        setNotice({ tone: "error", text: "Sign in again before linking an account." });
        return;
      }

      const alreadyLinked = auth.currentUser.providerData.some((item) => item.providerId === provider);
      setPending({ provider, step: alreadyLinked ? "confirm" : "open" });
      setNotice(alreadyLinked ? confirmNotice(provider) : {
        tone: "info",
        text: `Select Open ${labProviderNames[provider]} and sign in to the account you want to link.`,
      });
    } catch {
      setNotice({ tone: "error", text: "Could not check your session. Sign in again before linking." });
    } finally {
      setBusy(false);
    }
  };

  const link = async ({ provider, step }: PendingLink) => {
    setBusy(true);
    setNotice(null);
    try {
      const user = getLabAuth().currentUser;
      if (!user) {
        setPending(null);
        setNotice({ tone: "error", text: "Sign in again before linking an account." });
        return;
      }
      const oauthProvider = createLabOAuthProvider(provider);
      if (step === "open") {
        await linkWithPopup(user, oauthProvider);
        setPending({ provider, step: "confirm" });
        setNotice(confirmNotice(provider));
        return;
      }

      const proof = await reauthenticateWithPopup(user, oauthProvider);
      const response = await fetch("/lab/session/link", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, idToken: await proof.user.getIdToken() }),
      });
      if (!response.ok) {
        setNotice({ tone: "error", text: response.status >= 500
          ? "Could not check the link. Try confirming again."
          : "Could not confirm this link. Sign in again and choose the same account when you confirm." });
        return;
      }

      setPending(null);
      setConfirmed((providers) => [...providers, provider]);
      setNotice({ tone: "success", text: `${labProviderNames[provider]} is linked. You can use it the next time you sign in.` });
    } catch (error) {
      if (step === "open" && error instanceof FirebaseError && error.code === "auth/provider-already-linked") {
        setPending({ provider, step: "confirm" });
        setNotice(confirmNotice(provider));
        return;
      }
      setNotice({ tone: "error", text: linkIssue(error, provider) });
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const response = await fetch("/lab/session", { method: "DELETE", credentials: "same-origin" });
      if (!response.ok) throw new Error("Logout failed");
      await signOut(getLabAuth());
      router.replace("/lab/login");
      router.refresh();
    } catch {
      setNotice({ tone: "error", text: "Unable to sign out. Try again." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.accountActions} aria-labelledby="lab-linked-identities">
      <h2 id="lab-linked-identities">Linked accounts</h2>
      <p className={styles.hint}>
        Link an account within {LAB_RECENT_LOGIN_SECONDS / 60} minutes of signing in. <Link href="/lab/login">Sign in again</Link> if you reload this page.
      </p>
      {notice && (
        <p
          className={`${styles.notice} ${notice.tone === "info" ? "" : styles[notice.tone]}`}
          role={notice.tone === "error" ? "alert" : "status"}
        >
          {notice.text}
        </p>
      )}
      <ul className={styles.providerList}>
        {labSignInProviders.map((provider) => {
          const name = labProviderNames[provider];
          const isLinked = linkedProviders?.includes(provider) || confirmed.includes(provider);
          const providerStep = pending?.provider === provider ? pending : null;
          let status = linkedProviders ? "Not linked" : "Status unavailable";
          if (providerStep?.step === "confirm") status = "Awaiting confirmation";
          if (isLinked) status = "Linked";

          return (
            <li key={provider} className={styles.providerRow}>
              <div className={styles.providerIdentity}>
                <ProviderIcon provider={provider} />
                <div>
                  <p className={styles.providerLabel}>{name}</p>
                  <p className={`${styles.providerState} ${isLinked ? styles.linked : ""}`}>
                    {status}
                  </p>
                </div>
              </div>
              {!isLinked && (
                <button
                  type="button"
                  className={styles.secondaryButton}
                  disabled={busy}
                  onClick={() => void (providerStep ? link(providerStep) : prepare(provider))}
                >
                  {providerStep ? (providerStep.step === "open" ? "Open" : "Confirm") : "Link"} {name}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      <button type="button" className={`${styles.secondaryButton} ${styles.signOut}`} disabled={busy} onClick={() => void logout()}>
        Sign out
      </button>
    </section>
  );
}
