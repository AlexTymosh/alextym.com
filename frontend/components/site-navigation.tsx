"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { siteConfig } from "../lib/site-config";
import { ThemeToggle } from "./theme-toggle";

export function SiteNavigation() {
  const pathname = usePathname();
  const brandLabel = siteConfig.name.toUpperCase();

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="brand-mark" aria-label={`${brandLabel} home`}>
          <span className="brand-mark__braces">{"{ }"}</span>
          <span>{brandLabel}</span>
        </Link>
        <nav className="nav-pill" aria-label="Main navigation">
          {siteConfig.navigation.map((item) => {
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={isActive ? "nav-pill__link nav-pill__link--active" : "nav-pill__link"}
                aria-current={isActive ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
