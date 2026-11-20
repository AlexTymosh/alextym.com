"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AccountAvatar } from "./account-avatar";
import { SignOutButton } from "./sign-out-button";
import styles from "./settings.module.css";

export function SettingsShell({ children, name, avatarUrl, owner }: {
  children: ReactNode; name: string; avatarUrl: string | null; owner: boolean;
}) {
  const pathname = usePathname();
  const items = [
    { href: "/settings", label: "Available projects" },
    { href: "/settings/profile", label: "Profile" },
    { href: "/settings/connections", label: "Sign-in methods" },
    ...(owner ? [{ href: "/settings/access", label: "Access management" }] : []),
  ];
  function links() {
    return items.map((item) => <Link key={item.href} href={item.href}
      aria-current={pathname === item.href ? "page" : undefined}>{item.label}</Link>);
  }
  return (
    <div className={styles.settings}>
      <aside className={styles.sidebar}>
        <Link className={styles.identity} href="/settings/profile">
          <AccountAvatar name={name} url={avatarUrl} size={44} />
          <span>{name}</span>
        </Link>
        <nav className={styles.sideLinks} aria-label="Settings navigation">{links()}</nav>
        <SignOutButton className={styles.signOut} />
      </aside>
      <div className={styles.workspace}>
        <header className={styles.header}><h1>Settings</h1></header>
        <nav className={styles.tabs} aria-label="Settings sections">{links()}</nav>
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
