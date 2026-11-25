"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AccountSessionProvider } from "./account-session";
import { DemoSiteBar } from "./demo-site-bar";
import demoStyles from "./demo-site-bar.module.css";

const workforcePath = "/portfolio/workforce-intelligence";
const fleetPath = "/portfolio/fleet-vor-hub";

export function SiteFrame({ children, navigation, footer }: Readonly<{
  children: ReactNode;
  navigation: ReactNode;
  footer: ReactNode;
}>) {
  const pathname = usePathname();
  if (pathname === workforcePath || pathname?.startsWith(`${workforcePath}/`)) {
    return <div className={`${demoStyles.frame} ${demoStyles.fullPage}`}>
      <DemoSiteBar />{children}
    </div>;
  }
  const fleet = pathname === fleetPath || pathname?.startsWith(`${fleetPath}/`);

  return (
    <AccountSessionProvider><div className={`app-shell${fleet ? ` ${demoStyles.frame}` : ""}`}>
      {fleet && <DemoSiteBar />}
      {navigation}
      <main className="site-main" data-preferans={pathname === "/portfolio/preferans" ? "true" : undefined}>{children}</main>
      {footer}
    </div></AccountSessionProvider>
  );
}
