"use client";

import { useState } from "react";
import { FirebaseError } from "firebase/app";
import { useRouter } from "next/navigation";
import { linkWithPopup, reauthenticateWithPopup } from "firebase/auth";
import type { LabOAuthProvider } from "../lib/portfolio-lab/admission-policy";
import { labOAuthIssue, labProviderNames, labSignInProviders } from "../lib/portfolio-lab/auth-ui";
import { createLabOAuthProvider, getLabAuth } from "../lib/portfolio-lab/firebase-client";
import { AccountReauthentication } from "./account-reauthentication";
import { ProviderIcon } from "./provider-icon";
import styles from "./lab-auth.module.css";
import { useClientReady } from "../lib/use-client-ready";

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

export function LabAccountActions({ linkedProviders, identity }: {
  linkedProviders: LabOAuthProvider[] | null;
  identity: { uid: string; email: string; passwordEnabled: boolean };
}) {
  const router = useRouter();
  const ready = useClientReady();
  const [notice, setNotice] = useState<LinkNotice | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<LabOAuthProvider | null>(null);
  const [confirmed, setConfirmed] = useState<LabOAuthProvider[]>([]);
  const [verifyTarget, setVerifyTarget] = useState<LabOAuthProvider | null>(null);

  const link = async (provider: LabOAuthProvider) => {
    setBusy(true);
    setNotice(null);
    try {
      const user = getLabAuth().currentUser;
      if (!user || user.uid !== identity.uid) {
        setPending(null);
        setVerifyTarget(provider);
        return;
      }
      const oauthProvider = createLabOAuthProvider(provider);
      if (pending !== provider && !user.providerData.some((item) => item.providerId === provider)) {
        // Open during this click, before a network request can consume the user gesture.
        await linkWithPopup(user, oauthProvider);
        setPending(provider);
        setNotice(confirmNotice(provider));
        return;
      }

      const proof = await reauthenticateWithPopup(user, oauthProvider);
      const response = await fetch("/auth/session/link", {
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
      router.refresh();
    } catch (error) {
      if (error instanceof FirebaseError && error.code === "auth/provider-already-linked") {
        setPending(provider);
        setNotice(confirmNotice(provider));
        return;
      }
      setNotice({ tone: "error", text: linkIssue(error, provider) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.accountActions} aria-labelledby="lab-linked-identities">
      <h2 id="lab-linked-identities">Linked accounts</h2>
      <p className={styles.hint}>
        Add another sign-in method whenever you need it. We may ask you to confirm your identity.
      </p>
      {verifyTarget && <AccountReauthentication uid={identity.uid} email={identity.email}
        providers={linkedProviders || []} passwordEnabled={identity.passwordEnabled}
        onCancel={() => setVerifyTarget(null)} onVerified={() => {
          setVerifyTarget(null);
          setNotice({ tone: "info", text: `Identity confirmed. Select ${pending === verifyTarget ? "Confirm" : "Link"} ${labProviderNames[verifyTarget]} to continue.` });
          router.refresh();
        }} />}
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
          let status = linkedProviders ? "Not linked" : "Status unavailable";
          if (pending === provider) status = "Awaiting confirmation";
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
                  disabled={!ready || busy}
                  onClick={() => void link(provider)}
                >
                  {pending === provider ? "Confirm" : "Link"} {name}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
