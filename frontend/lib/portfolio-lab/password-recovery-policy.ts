/** Pure, testable policy. A reset code is a credential, never a grant. */
export type ResetUser = { uid: string; email: string; disabled: boolean };
export type ResetCodeCheck = { email: string; requestType: string };
export type PasswordResetEffects = {
  inspect: (code: string) => Promise<ResetCodeCheck | null>;
  lookupUser: (email: string) => Promise<ResetUser>;
  loadRecord: (uid: string) => Promise<unknown>;
  begin: (uid: string) => Promise<void>;
  confirm: (code: string, newPassword: string) => Promise<ResetCodeCheck | null>;
  revoke: (uid: string) => Promise<void>;
  commit: (uid: string) => Promise<void>;
};

export function validResetCode(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9._~-]{10,4096}$/.test(value);
}

export function validNewPassword(value: unknown): value is string {
  return typeof value === "string" &&
    value.length >= 12 && value.length <= 128 && !Array.from(value).some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127);
}

export function eligibleForPasswordRecovery(uid: string, ownerUid: string, record: unknown): boolean {
  if (!uid || uid.includes("/") || !ownerUid || uid === ownerUid) return false;
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const data = record as Record<string, unknown>;
  return data.schema_version === 1 && data.uid === uid &&
    ["invited", "active"].includes(String(data.status)) &&
    ["initial", "user_set", "none"].includes(String(data.password_state));
}

/**
 * After a valid Firebase code and trusted UID admission have been checked,
 * atomically enter reset_pending BEFORE changing the Firebase password.
 * Any ambiguous provider, revocation or Firestore failure leaves password
 * admission denied. Recovery requires a separately audited Owner repair.
 */
export function eligibleForPasswordCompletion(uid: string, ownerUid: string, record: unknown): boolean {
  if (!uid || uid.includes("/") || !ownerUid || uid === ownerUid) return false;
  if (!record || typeof record !== "object" || Array.isArray(record)) return false;
  const data = record as Record<string, unknown>;
  return data.schema_version === 1 && data.uid === uid &&
    ["invited", "active"].includes(String(data.status)) &&
    data.password_state === "reset_pending";
}

export async function completePasswordReset(
  effects: PasswordResetEffects,
  code: string,
  password: string,
  ownerUid: string,
): Promise<"success" | "invalid"> {
  if (!validResetCode(code) || !validNewPassword(password) || !ownerUid) return "invalid";
  const inspected = await effects.inspect(code);
  if (!inspected || inspected.requestType !== "PASSWORD_RESET" || !inspected.email) return "invalid";
  const before = await effects.lookupUser(inspected.email);
  if (before.disabled || !eligibleForPasswordRecovery(
    before.uid, ownerUid, await effects.loadRecord(before.uid),
  )) return "invalid";

  // The durable transition must fail closed; a provider password mutation
  // must never precede the reset_pending admission lock.
  await effects.begin(before.uid);
  const confirmed = await effects.confirm(code, password);
  if (!confirmed || confirmed.requestType !== "PASSWORD_RESET" ||
      confirmed.email.toLowerCase() !== inspected.email.toLowerCase()) return "invalid";

  const after = await effects.lookupUser(inspected.email);
  if (after.uid !== before.uid || after.disabled) return "invalid";
  // Revocation is required before unlocking user_set. An old signed session
  // must not survive simply because the Firestore password marker changed.
  await effects.revoke(before.uid);
  // The transactional commit must recheck status/UID to prevent revoked user
  // admission, even if the account was disabled during provider confirmation.
  await effects.commit(before.uid);
  return "success";
}
