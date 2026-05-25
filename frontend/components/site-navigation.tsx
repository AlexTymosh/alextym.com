"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./theme-toggle";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/resume", label: "Resume" },
  { href: "/chat", label: "Chat" },
  { href: "/contact", label: "Contact" },
];

export function SiteNavigation() {
  const pathname = usePathname();

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="brand-mark" aria-label="ALEXTYM.COM home">
          <span className="brand-mark__braces">{"{ }"}</span>
          <span>ALEXTYM.COM</span>
        </Link>
        <nav className="nav-pill" aria-label="Main navigation">
          {navigation.map((item) => {
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
