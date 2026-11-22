import type { LabOAuthProvider } from "./admission-policy";

export const labProviderNames = {
  "google.com": "Google",
  "microsoft.com": "Microsoft",
  "github.com": "GitHub",
  "facebook.com": "Facebook",
} as const satisfies Record<LabOAuthProvider, string>;

export const labSignInProviders = (Object.keys(labProviderNames) as LabOAuthProvider[])
  .filter((provider) => (provider !== "facebook.com" ||
    process.env.NEXT_PUBLIC_FIREBASE_FACEBOOK_ENABLED === "true") &&
    (provider !== "github.com" || process.env.NEXT_PUBLIC_FIREBASE_GITHUB_ENABLED === "true"));

export function labOAuthIssue(provider: LabOAuthProvider, code: string | undefined): string | undefined {
  const name = labProviderNames[provider];
  switch (code) {
    case "auth/popup-blocked":
      return `Allow pop-ups for this site, then try ${name} again.`;
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
      return `The ${name} window closed before login finished. Open it again to continue.`;
    case "auth/operation-not-allowed":
    case "auth/unauthorized-domain":
      return `${name} login is unavailable on this site. You can log in with email.`;
    case "auth/network-request-failed":
      return `Could not reach ${name}. Check your connection and try again.`;
    case "auth/user-mismatch":
      return `Choose the same ${name} account you used to start linking.`;
    default:
      return undefined;
  }
}
