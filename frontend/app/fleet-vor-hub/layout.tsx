import { requireLabProjectPage } from "../../lib/portfolio-lab/project-access-server";

export const dynamic = "force-dynamic";

export default async function FleetLayout({ children }: { children: React.ReactNode }) {
  await requireLabProjectPage("fleet_hub");
  return children;
}
