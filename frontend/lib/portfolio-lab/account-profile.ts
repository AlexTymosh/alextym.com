import type { LabOAuthProvider } from "./admission-policy";

export type AccountProfile = {
  firstName: string;
  lastName: string;
  displayName: string;
  email: string;
  avatarUrl: string | null;
  avatarSource: string;
  revision: number;
  linkedProviders: LabOAuthProvider[];
  providerPhotos: { provider: LabOAuthProvider; url: string }[];
};

export function validProfileName(value: unknown): value is string {
  return typeof value === "string" && value.length <= 80 &&
    !/[\u0000-\u001f\u007f-\u009f]/.test(value);
}

export function providerPhotoUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2048) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}
