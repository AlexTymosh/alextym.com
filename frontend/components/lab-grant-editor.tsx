"use client";

import { useState, type FormEvent } from "react";
import { projectRoles, type ProjectRole } from "../lib/portfolio-lab/project-grants";
import styles from "./lab-auth.module.css";

export function LabGrantEditor({ uid, projectId, title, role, revision, disabled }: {
  uid: string; projectId: string; title: string; role: string; revision: number; disabled: boolean;
}) {
  const [version, setVersion] = useState(revision);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState(false);

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("role") as ProjectRole | "No Access";
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch("/auth/access/grants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid, projectId, role: value, revision: version }),
      });
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        setFailed(true);
        setNotice(result?.code === "RECENT_LOGIN_REQUIRED" ? "Sign in again before changing access."
          : response.status === 409 ? "This account or grant changed. Reload the page before saving."
          : "Could not save access. Try again.");
        return;
      }
      setVersion(result.revision);
      setFailed(false);
      setNotice(value === "No Access" ? "Access revoked." : `${value} access saved.`);
    } catch {
      setFailed(true);
      setNotice("Could not save access. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className={styles.grantForm} onSubmit={save}>
      <label className={styles.field}>
        <span className={styles.srOnly}>{title}</span>
        <select name="role" defaultValue={role} disabled={disabled || busy}>
          {["No Access", ...projectRoles].map((option) => <option key={option}>{option}</option>)}
        </select>
      </label>
      <button className={styles.secondaryButton} disabled={disabled || busy} type="submit">
        {busy ? "Saving…" : "Save access"}
      </button>
      {notice && <p className={styles.hint} role={failed ? "alert" : "status"}>{notice}</p>}
    </form>
  );
}
