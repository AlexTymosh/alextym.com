"use client";

import { useState } from "react";
import { useClientReady } from "../lib/use-client-ready";

export function SignOutButton({ className }: { className?: string }) {
  const ready = useClientReady();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  async function leave() {
    setBusy(true);
    setFailed(false);
    try {
      const response = await fetch("/auth/session", { method: "DELETE", credentials: "same-origin" });
      if (!response.ok) throw new Error();
      // A fresh document also clears the Firebase credential kept only in memory.
      window.location.replace("/sign-in");
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }
  return <div>
    <button type="button" className={className} disabled={!ready || busy} onClick={() => void leave()}>
      {busy ? "Logging out…" : "Log Out"}
    </button>
    {failed && <p role="alert">Unable to log out. Try again.</p>}
  </div>;
}
