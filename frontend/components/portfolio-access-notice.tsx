"use client";

import Link from "next/link";
import { useAccountSession } from "./account-session";
import styles from "../app/portfolio/page.module.css";

export function PortfolioAccessNotice() {
  const { status } = useAccountSession();
  const loggedIn = status === "authenticated";
  return <aside className={styles.accessNotice} aria-label="Demo access">
    <span>{loggedIn ? "View your available projects or request access to another demo."
      : "Interactive demos require login and permission for each project."}</span>
    {status === "loading" ? <span role="status">Checking account…</span>
      : <Link href={loggedIn || status === "unavailable" ? "/settings" : "/sign-in"}>
        {loggedIn ? "View your projects" : status === "unavailable" ? "Settings" : "Log In"}
      </Link>}
    <Link href="/contact">Request access</Link>
  </aside>;
}
