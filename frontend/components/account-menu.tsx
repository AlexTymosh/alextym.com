"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AccountAvatar } from "./account-avatar";
import { useAccountSession } from "./account-session";

export function AccountMenu() {
  const pathname = usePathname();
  const { account, status } = useAccountSession();
  if (status === "loading" || status === "disabled") return null;
  return <Link href={status === "guest" ? "/sign-in" : "/settings"} className="nav-account"
    aria-current={pathname?.startsWith("/settings") ? "page" : undefined}>
    {account && <AccountAvatar name={account.displayName} url={account.avatarUrl} size={28} />}
    <span>{account?.displayName || (status === "guest" ? "Log In" : "Settings")}</span>
  </Link>;
}
