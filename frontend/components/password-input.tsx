"use client";

import { useState, type InputHTMLAttributes } from "react";
import styles from "./lab-auth.module.css";

export function PasswordInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <div className={styles.passwordInput}>
      <input {...props} type={visible ? "text" : "password"} />
      <button type="button" className={styles.passwordToggle}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible} aria-controls={props.id} disabled={props.disabled}
        onClick={() => setVisible((value) => !value)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {visible && <path d="m3 3 18 18" />}
        </svg>
      </button>
    </div>
  );
}
