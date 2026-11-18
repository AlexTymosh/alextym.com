import { projectRoles, type ProjectRole } from "./project-grants";

export type GrantChange = {
  uid: string;
  projectId: string;
  role: ProjectRole | "No Access";
  revision: number;
};

export function grantChange(body: Record<string, unknown> | null, projectIds: string[]): GrantChange | null {
  if (!body || Object.keys(body).some((key) => !["uid", "projectId", "role", "revision"].includes(key))) return null;
  if (typeof body.uid !== "string" || !body.uid || body.uid.length > 128 ||
      body.uid.includes("/") || body.uid === "." || body.uid === ".." ||
      typeof body.projectId !== "string" || !projectIds.includes(body.projectId) ||
      !["No Access", ...projectRoles].some((role) => role === body.role) ||
      typeof body.revision !== "number" || !Number.isSafeInteger(body.revision) || body.revision < 0) return null;
  return body as GrantChange;
}
