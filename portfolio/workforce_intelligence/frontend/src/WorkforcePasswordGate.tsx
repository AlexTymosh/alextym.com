"use client";

import { useEffect, useState, type FormEvent } from "react";
import Image from "next/image";
import { WorkforceScaffold } from "./WorkforceScaffold";
import styles from "./workforce-password.module.css";

const ACCESS = "/portfolio/workforce-intelligence/api/access";

type State = "loading" | "locked" | "unlocked" | "error";

export function WorkforcePasswordGate({ loginPath }: { loginPath?: string } = {}) {
  const [state, setState] = useState<State>("loading");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void fetch(ACCESS, { cache: "no-store", credentials: "same-origin", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to check the demo session.");
        const result = await response.json() as { authenticated: boolean };
        if (!controller.signal.aborted) setState(result.authenticated ? "unlocked" : "locked");
      })
      .catch(() => { if (!controller.signal.aborted) { setMessage("Access service unavailable. Retry shortly."); setState("error"); } });
    return () => controller.abort();
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(ACCESS, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(data?.detail ?? "Unable to log in.");
      }
      setPassword("");
      setState("unlocked");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to log in.");
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    try {
      const response = await fetch(ACCESS, { method: "DELETE", credentials: "same-origin" });
      if (!response.ok) throw new Error("Logout unavailable. Retry.");
      if (loginPath) {
        window.location.assign(loginPath);
        return;
      }
      setState("locked");
      setMessage("");
    } catch {
      setState("error");
      setMessage("Logout could not be confirmed. Retry or close the browser.");
    }
  };

  if (state === "unlocked") return <main><WorkforceScaffold onSignOut={() => void signOut()} /></main>;
  if (state === "loading") return <main className={styles.loading}><p role="status">Checking demo access…</p></main>;

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <section className={styles.intro} aria-labelledby="wi-intro-heading">
          <Image className={styles.logo} src="/workforce-simulation-logo.png" alt="Workforce Analytics Simulation Environment emblem" width={256} height={256} priority />
          <p className={styles.eyebrow}>Portfolio demonstration · Synthetic data only</p>
          <h1 id="wi-intro-heading">Workforce &amp; Recruitment Intelligence</h1>
          <p>An interactive demonstration of workforce KPIs, recruitment funnels, vacancy ageing and data quality.</p>
          <p>Built for the 16 November interview.</p>
        </section>
        <section className={styles.access} aria-labelledby="wi-access-heading">
          <h2 id="wi-access-heading">Demo access</h2>
          {state === "error" ? (
            <button type="button" className={styles.button} onClick={() => window.location.reload()}>Retry</button>
          ) : (
            <form onSubmit={(event) => void submit(event)}>
              <label htmlFor="wi-password">Demo password</label>
              <input id="wi-password" name="password" type="password" required maxLength={128}
                autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
              <button className={styles.button} type="submit" disabled={busy}>
                {busy ? "Checking…" : "Enter demo"}
              </button>
            </form>
          )}
          {message && <p className={styles.error} role="alert">{message}</p>}
        </section>
      </div>
    </main>
  );
}
