/** Admission is identity-level only. No project role or capability is granted here. */
export type LabAdmissionDecision = "allowed" | "denied" | "password_expired";

export const labOAuthProviders = ["google.com", "github.com", "microsoft.com"] as const;
export type LabOAuthProvider = (typeof labOAuthProviders)[number];

type LabClaims = {
  uid?: unknown;
  firebase?: { sign_in_provider?: unknown; identities?: unknown };
};

export function isLabOAuthProvider(value: unknown): value is LabOAuthProvider {
  return labOAuthProviders.some((provider) => provider === value);
}

export function labOAuthSubject(claims: LabClaims, provider: LabOAuthProvider): string | undefined {
  const identities = claims.firebase?.identities;
  if (!identities || typeof identities !== "object") return;
  const subjects = (identities as Record<string, unknown>)[provider];
  if (Array.isArray(subjects) && subjects.length === 1 &&
      typeof subjects[0] === "string" && subjects[0]) return subjects[0];
}

export function labOAuthBindings(record: Record<string, unknown>): Partial<Record<LabOAuthProvider, string>> {
  const bindings = record.oauth_provider_subjects;
  if (!bindings || typeof bindings !== "object" || Array.isArray(bindings)) return {};
  const entries = bindings as Record<string, unknown>;
  const result: Partial<Record<LabOAuthProvider, string>> = {};
  for (const provider of labOAuthProviders) {
    const subject = entries[provider];
    if (typeof subject === "string" && subject) result[provider] = subject;
  }
  return result;
}

export function labAdmissionDecision(
  uid: string,
  ownerUid: string,
  provider: string,
  record: unknown,
  nowMs: number,
  authTime?: number,
  subject?: string,
): LabAdmissionDecision {
  if (typeof uid !== "string" || !uid || !ownerUid) return "denied";
  if (provider === "password" && uid === ownerUid) return "allowed";
  if (typeof record !== "object" || record === null || Array.isArray(record)) return "denied";
  const data = record as Record<string, unknown>;
  if (
    data.schema_version !== 1 ||
    data.uid !== uid ||
    data.status !== "active"
  ) return "denied";
  for (const field of ["password_changed_at_ms", "password_reset_repaired_at_ms"]) {
    if (!Object.hasOwn(data, field)) continue;
    const timestamp = data[field];
    if (!validTimestamp(timestamp) || typeof authTime !== "number" ||
        !Number.isSafeInteger(authTime) || authTime <= Math.floor(timestamp / 1000)) return "denied";
  }

  if (provider !== "password") {
    if (!isLabOAuthProvider(provider) || !subject || labOAuthBindings(data)[provider] !== subject) {
      return "denied";
    }
    return ["initial", "user_set", "none", "reset_pending"].some((state) => state === data.password_state)
      ? "allowed" : "denied";
  }
  if (data.password_state === "user_set") return "allowed";
  if (data.password_state !== "initial") return "denied";
  const expires = data.initial_password_expires_at_ms;
  if (!validTimestamp(expires)) return "denied";
  return nowMs >= expires ? "password_expired" : "allowed";
}

function validTimestamp(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) &&
    value > 0 && value < 8_640_000_000_000_000;
}

export function labSignInProvider(claims: LabClaims): string {
  const provider = claims.firebase?.sign_in_provider;
  return typeof provider === "string" ? provider : "";
}
