import { notFound, redirect } from "next/navigation";
import type { ReactNode } from "react";
import { SettingsShell } from "../../components/settings-shell";
import { getAccountProfile } from "../../lib/portfolio-lab/account-profile-server";
import { currentLabSession } from "../../lib/portfolio-lab/project-access-server";
import { getOwnerUid, isLabEnabled } from "../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Settings", robots: { index: false, follow: false } };

export default async function SettingsLayout({ children }: { children: ReactNode }) {
  if (!isLabEnabled()) notFound();
  const session = await currentLabSession();
  if (!session) redirect("/sign-in");
  const profile = await getAccountProfile(session.uid);
  return <SettingsShell name={profile.displayName} avatarUrl={profile.avatarUrl}
    owner={session.uid === getOwnerUid()}>{children}</SettingsShell>;
}
