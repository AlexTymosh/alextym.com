"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import type { AccountProfile } from "../lib/portfolio-lab/account-profile";

type AccountSession = {
  status: "loading" | "authenticated" | "guest" | "disabled" | "unavailable";
  account: Pick<AccountProfile, "displayName" | "avatarUrl"> | null;
};
const AccountSessionContext = createContext<AccountSession>({ status: "loading", account: null });

export function AccountSessionProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [session, setSession] = useState<AccountSession>({ status: "loading", account: null });
  useEffect(() => {
    let active = true;
    let revision = 0;
    async function refresh() {
      const current = ++revision;
      try {
        const response = await fetch("/auth/profile", { cache: "no-store" });
        const account = response.ok ? await response.json() : null;
        const status = response.ok ? "authenticated" : response.status === 404 ? "disabled"
          : response.status === 401 || response.status === 403 ? "guest" : "unavailable";
        if (active && current === revision) setSession({ status, account });
      } catch {
        if (active && current === revision) setSession({ status: "unavailable", account: null });
      }
    }
    void refresh();
    window.addEventListener("account-profile-updated", refresh);
    return () => { active = false; window.removeEventListener("account-profile-updated", refresh); };
  }, [pathname]);
  return <AccountSessionContext.Provider value={session}>{children}</AccountSessionContext.Provider>;
}

export function useAccountSession() { return useContext(AccountSessionContext); }
