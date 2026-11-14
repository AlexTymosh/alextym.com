"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { validNewPassword, validResetCode, validResetUid } from "../lib/portfolio-lab/password-recovery-policy";

export function LabPasswordReset() {
  const [link, setLink] = useState<{ uid: string; code: string } | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  // Preserve the URL code across React Strict Mode's extra effect cycle.
  const capturedLink = useRef<{ uid: string | null; code: string | null } | null>(null);

  useEffect(() => {
    if (capturedLink.current === null) {
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      capturedLink.current = { uid: fragment.get("uid"), code: fragment.get("oobCode") };
      // Remove the one-time code from the visible URL before using it.
      window.history.replaceState(null, "", "/lab/password/reset");
    }

    // Schedule the UI update after the effect; avoid synchronous setState.
    queueMicrotask(() => {
      const supplied = capturedLink.current;
      if (supplied && validResetUid(supplied.uid) && validResetCode(supplied.code)) {
        setLink({ uid: supplied.uid, code: supplied.code });
      } else {
        setMessage("Invalid link. Request a new setup link from the Owner.");
      }
    });
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!link) return;
    if (password !== confirm || !validNewPassword(password)) {
      setMessage("Passwords must match and contain 12–128 valid characters.");
      return;
    }
    setBusy(true); setMessage("");
    try {
      const response = await fetch("/lab/password/reset/action", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid: link.uid, oobCode: link.code, newPassword: password }),
      });
      if (!response.ok) throw new Error("Reset did not complete");
      capturedLink.current = null;
      setLink(null); setPassword(""); setConfirm(""); setDone(true);
      setMessage("Password updated. You can now sign in.");
    } catch {
      setMessage("Reset could not be completed. Request a fresh link from the Owner.");
    } finally { setBusy(false); }
  };

  return (
    <section style={{ maxWidth: 450, margin: "3rem auto", padding: "1rem" }}>
      <h1>Set your Portfolio Lab password</h1>
      <p>Use your private one-time link. Passwords must contain 12–128 characters.</p>
      {!done && link && (
        <form onSubmit={(event) => void submit(event)}>
          <label htmlFor="lab-new-password">New password</label>
          <input id="lab-new-password" type="password" autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} style={{ display: "block", width: "100%", marginBottom: 12 }} />
          <label htmlFor="lab-confirm-password">Confirm password</label>
          <input id="lab-confirm-password" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} style={{ display: "block", width: "100%", marginBottom: 12 }} />
          <button type="submit" disabled={busy}>Set password</button>
        </form>
      )}
      {message && <p role="status">{message}</p>}
      {done && <a href="/lab/login">Go to sign in</a>}
    </section>
  );
}
