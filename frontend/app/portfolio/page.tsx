import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { workforceEnabled } from "../../lib/portfolio-lab/workforce-password-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Portfolio demonstrations",
  robots: { index: false, follow: false },
};

export default function PortfolioCataloguePage() {
  if (!workforceEnabled()) notFound();
  return (
    <main>
      <h1>Portfolio demonstrations</h1>
      <p>Independent synthetic-data projects.</p>
      <ul><li><Link href="/portfolio/workforce-intelligence">Workforce &amp; Recruitment Intelligence</Link></li></ul>
    </main>
  );
}
