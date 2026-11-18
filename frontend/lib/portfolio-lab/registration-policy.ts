import { isLabOAuthProvider, labOAuthSubject, labSignInProvider } from "./admission-policy";

type RegistrationClaims = {
  uid?: string;
  firebase?: { sign_in_provider?: unknown; identities?: unknown };
};

type RegistrationUser = {
  uid: string;
  disabled: boolean;
  providerData: { providerId: string; uid: string }[];
};

/** A verified initial credential creates account access with no project grants. */
export function newLabIdentity(claims: RegistrationClaims, user: RegistrationUser, nowMs: number) {
  if (!claims.uid || claims.uid !== user.uid || claims.uid.includes("/") || user.disabled) return null;
  const provider = labSignInProvider(claims);
  const subject = isLabOAuthProvider(provider) ? labOAuthSubject(claims, provider) : undefined;
  if (!user.providerData.some((identity) => identity.providerId === provider &&
      (provider === "password" || identity.uid === subject))) return null;
  if (provider !== "password" && (!isLabOAuthProvider(provider) || !subject)) return null;

  return {
    schema_version: 1,
    uid: claims.uid,
    status: "active",
    password_state: provider === "password" ? "user_set" : "none",
    oauth_provider_subjects: subject ? { [provider]: subject } : {},
    registration_source: "self_service",
    registered_at_ms: nowMs,
  };
}
