"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { AccountProfile } from "../lib/portfolio-lab/account-profile";
import { AccountAvatar } from "./account-avatar";

export function AccountMenu() {
  const pathname = usePathname();
  const [account, setAccount] = useState<Pick<AccountProfile, "displayName" | "avatarUrl"> | null>(null);
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const response = await fetch("/auth/profile", { cache: "no-store" });
        const profile = response.ok ? await response.json() : null;
        if (active) { setEnabled(response.status !== 404); setAccount(profile); }
      } catch {
        if (active) setAccount(null);
      }
    }
    void refresh();
    window.addEventListener("account-profile-updated", refresh);
    return () => { active = false; window.removeEventListener("account-profile-updated", refresh); };
  }, [pathname]);
  if (!enabled) return null;
  return <Link href={account ? "/settings" : "/sign-in"} className="nav-account"
    aria-current={pathname?.startsWith("/settings") ? "page" : undefined}>
    {account && <AccountAvatar name={account.displayName} url={account.avatarUrl} size={28} />}
    <span>{account?.displayName || "Sign in"}</span>
  </Link>;
}
