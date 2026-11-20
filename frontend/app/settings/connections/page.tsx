import { redirect } from "next/navigation";
import { LabAccountActions } from "../../../components/lab-account-actions";
import { getLabLinkedProviders } from "../../../lib/portfolio-lab/lab-admission-server";
import { currentLabSession } from "../../../lib/portfolio-lab/project-access-server";
import { isLabOAuthProvider, labSignInProvider } from "../../../lib/portfolio-lab/admission-policy";
import { labProviderNames } from "../../../lib/portfolio-lab/auth-ui";
import styles from "../../../components/settings.module.css";

export default async function ConnectionsPage() {
  const session = await currentLabSession();
  if (!session) redirect("/sign-in");
  const provider = labSignInProvider(session);
  const name = isLabOAuthProvider(provider) ? labProviderNames[provider] : "email and password";
  const linked = await getLabLinkedProviders(session.uid);
  return <div className={styles.providerSection}>
    <div><h2>Sign-in methods</h2><p className={styles.description}>Signed in with {name}</p></div>
    <LabAccountActions linkedProviders={linked} />
  </div>;
}
