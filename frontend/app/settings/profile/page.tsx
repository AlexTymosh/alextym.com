import { redirect } from "next/navigation";
import { AccountProfileForm } from "../../../components/account-profile-form";
import { getAccountProfile } from "../../../lib/portfolio-lab/account-profile-server";
import { currentLabSession } from "../../../lib/portfolio-lab/project-access-server";

export default async function ProfilePage() {
  const session = await currentLabSession();
  if (!session) redirect("/sign-in");
  return <AccountProfileForm profile={await getAccountProfile(session.uid)} />;
}
