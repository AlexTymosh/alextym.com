import { notFound } from "next/navigation";
import { LabLogin } from "../../components/lab-login";
import { isLabEnabled } from "../../lib/portfolio-lab/firebase-server";

export const dynamic = "force-dynamic";
export const metadata = { title: "Log In", robots: { index: false, follow: false } };

export default function SignInPage() {
  if (!isLabEnabled()) notFound();
  return <LabLogin />;
}
