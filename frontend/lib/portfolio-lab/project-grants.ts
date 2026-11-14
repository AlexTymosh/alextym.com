/** Shared platform policy; Workforce has one effective Member access level. */
export const WORKFORCE_PROJECT_ID = "workforce_intelligence";

type GrantRecord = Record<string, unknown>;

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
