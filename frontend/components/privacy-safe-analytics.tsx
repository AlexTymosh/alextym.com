"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { recordPageView } from "../lib/privacy-safe-analytics";

export function PrivacySafeAnalytics() {
  const pathname = usePathname();

  useEffect(() => {
    recordPageView(pathname);
  }, [pathname]);

  return null;
}
