/** Admission is identity-level only. No project role or capability is granted here. */
export type LabAdmissionDecision = "allowed" | "denied" | "password_expired";

const providers = new Set(["password", "google.com", "github.com", "microsoft.com"]);

type LabClaims = { uid?: unknown; firebase?: { sign_in_provider?: unknown } };

export function labAdmissionDecision(
  uid: string,
  ownerUid: string,
  provider: string,
  record: unknown,
  nowMs: number,
): LabAdmissionDecision {
  if (typeof uid !== "string" || !uid || !ownerUid) return "denied";
  if (uid === ownerUid) return "allowed";
  if (!providers.has(provider)) return "denied";
  if (typeof record !== "object" || record === null || Array.isArray(record)) return "denied";
  const data = record as Record<string, unknown>;
  if (
    data.schema_version !== 1 ||
    data.uid !== uid ||
    data.status !== "active"
  ) return "denied";
  if (!["initial", "user_set", "none"].includes(String(data.password_state))) return "denied";
  if (provider !== "password") return "allowed";
  if (data.password_state === "user_set") return "allowed";
  if (data.password_state === "none") return "denied";
  const expires = data.initial_password_expires_at_ms;
  if (
    typeof expires !== "number" ||
    !Number.isSafeInteger(expires) ||
    expires <= 0 ||
    expires >= 8_640_000_000_000_000
  ) return "denied";
  return nowMs >= expires ? "password_expired" : "allowed";
}

export function labSignInProvider(claims: LabClaims): string {
  const provider = claims.firebase?.sign_in_provider;
  return typeof provider === "string" ? provider : "";
}
