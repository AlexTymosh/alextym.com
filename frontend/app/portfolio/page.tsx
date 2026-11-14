import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { LAB_SESSION_COOKIE } from "../../lib/portfolio-lab/firebase-server";
import { getWorkforceAccess } from "../../lib/portfolio-lab/workforce-access-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Portfolio Lab projects",
  robots: { index: false, follow: false },
};

/** Catalogue only lists explicitly accessible, enabled project modules. */
export default async function PortfolioCataloguePage() {
  const cookie = (await cookies()).get(LAB_SESSION_COOKIE)?.value;
  const access = await getWorkforceAccess(cookie);
  if (access.kind === "unauthenticated") redirect("/lab/login");
  if (access.kind !== "allowed") notFound();
  return (
    <section>
      <h1>Portfolio Lab</h1>
      <p>Private synthetic demonstration projects.</p>
      <ul>
        <li>
          <Link href="/portfolio/workforce-intelligence">
            Workforce &amp; Recruitment Intelligence
          </Link>
        </li>
      </ul>
    </section>
  );
}
