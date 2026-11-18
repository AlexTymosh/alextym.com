/** Shared platform policy; Workforce has one effective Member access level. */
export const WORKFORCE_PROJECT_ID = "workforce_intelligence";

type GrantRecord = Record<string, unknown>;
export const projectRoles = ["View", "Test", "Admin"] as const;
export type ProjectRole = typeof projectRoles[number];

export function projectGrantRole(uid: string, projectId: string, record: unknown, nowMs: number): ProjectRole | null {
  if (!record || typeof record !== "object" || Array.isArray(record)) return null;
  const grant = record as GrantRecord;
  if (!uid || uid.includes("/") || !projectId || projectId.includes("/") ||
      !Number.isSafeInteger(nowMs) || grant.schema_version !== 1 || grant.uid !== uid ||
      grant.project_id !== projectId || grant.status !== "active" ||
      !projectRoles.some((role) => role === grant.role)) return null;
  if (Object.hasOwn(grant, "expires_at_ms") && (
    typeof grant.expires_at_ms !== "number" || !Number.isSafeInteger(grant.expires_at_ms) ||
    grant.expires_at_ms <= nowMs || grant.expires_at_ms >= 8_640_000_000_000_000
  )) return null;
  return grant.role as ProjectRole;
}

export function projectRoleAllows(role: ProjectRole | null, method: string, path: string): boolean {
  if (!role) return false;
  if (role === "Admin") return true;
  if (/\/demo\/(reset|seed)$|\/workflows(?:\/|$)/.test(path)) return false;
  if (method === "GET" || method === "HEAD") return true;
  return role === "Test";
}

export function adminGrantAllows(
  uid: string,
  projectId: string,
  record: unknown,
  nowMs: number,
): boolean {
  if (!uid || uid.includes("/") || !projectId || projectId.includes("/")) return false;
  if (!Number.isSafeInteger(nowMs) || !record || typeof record !== "object" || Array.isArray(record)) {
    return false;
  }
  const grant = record as GrantRecord;
  if (grant.schema_version !== 1 || grant.uid !== uid || grant.project_id !== projectId ||
      grant.status !== "active" || grant.role !== "Admin") return false;
  if (!Object.hasOwn(grant, "expires_at_ms")) return true;
  const expiry = grant.expires_at_ms;
  return typeof expiry === "number" && Number.isSafeInteger(expiry) &&
    expiry > 0 && expiry < 8_640_000_000_000_000 && nowMs < expiry;
}
