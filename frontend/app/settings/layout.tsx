import { notFound, redirect } from "next/navigation";
import type { ReactNode } from "react";
import { SettingsShell } from "../../components/settings-shell";
import { SettingsUnavailable } from "./unavailable";
import { getAccountProfile } from "../../lib/portfolio-lab/account-profile-server";
import { currentLabSession } from "../../lib/portfolio-lab/project-access-server";
import { getOwnerUid, isLabEnabled } from "../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Settings", robots: { index: false, follow: false } };

export default async function SettingsLayout({ children }: { children: ReactNode }) {
  if (!isLabEnabled()) notFound();
  const session = await currentLabSession().catch(() => undefined);
  if (session === undefined) return <SettingsUnavailable />;
  if (!session) redirect("/sign-in");

  const account = await getAccountProfile(session.uid)
    .then(profile => ({ profile, owner: session.uid === getOwnerUid() }))
    .catch(() => null);
  if (!account) return <SettingsUnavailable />;

  return <SettingsShell name={account.profile.displayName} avatarUrl={account.profile.avatarUrl}
    owner={account.owner}>{children}</SettingsShell>;
}
