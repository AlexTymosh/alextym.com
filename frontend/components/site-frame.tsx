"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AccountSessionProvider } from "./account-session";

const workforcePath = "/portfolio/workforce-intelligence";

export function SiteFrame({ children, navigation, footer }: Readonly<{
  children: ReactNode;
  navigation: ReactNode;
  footer: ReactNode;
}>) {
  const pathname = usePathname();
  if (pathname === workforcePath || pathname?.startsWith(`${workforcePath}/`)) {
    return children;
  }

  return (
    <AccountSessionProvider><div className="app-shell">
      {navigation}
      <main className="site-main">{children}</main>
      {footer}
    </div></AccountSessionProvider>
  );
}
