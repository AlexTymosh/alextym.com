import "server-only";

import { cache } from "react";
import { getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth } from "./firebase-server";
import { getLabLinkedProviders } from "./lab-admission-server";
import { isLabOAuthProvider } from "./admission-policy";
import { providerPhotoUrl, type AccountProfile } from "./account-profile";

export const getAccountProfile = cache(async (uid: string): Promise<AccountProfile> => {
  const auth = await getLabAdminAuth();
  const [user, document, approved] = await Promise.all([
    auth.getUser(uid),
    getFirestore(auth.app).collection("portfolio_lab_profiles").doc(uid).get(),
    getLabLinkedProviders(uid),
  ]);
  const stored = document.data();
  const providerPhotos = user.providerData.flatMap((provider) => {
    const url = providerPhotoUrl(provider.photoURL);
    return isLabOAuthProvider(provider.providerId) && approved.includes(provider.providerId) && url
      ? [{ provider: provider.providerId, url }] : [];
  });
  const name = user.displayName?.trim() || "";
  const [given = "", ...family] = name.split(/\s+/);
  const firstName = typeof stored?.first_name === "string" ? stored.first_name : given;
  const lastName = typeof stored?.last_name === "string" ? stored.last_name : family.join(" ");
  const avatarSource = typeof stored?.avatar_source === "string" ? stored.avatar_source : "account";
  const avatarUrl = avatarSource === "upload" && typeof stored?.avatar_data_url === "string"
    ? stored.avatar_data_url
    : avatarSource === "none" ? null
    : providerPhotos.find((photo) => photo.provider === avatarSource)?.url
      || providerPhotos[0]?.url || null;
  return {
    firstName, lastName, displayName: [firstName, lastName].filter(Boolean).join(" ") || "Your account",
    email: user.email || "", avatarUrl, avatarSource,
    revision: Number.isSafeInteger(stored?.revision) ? stored!.revision : 0,
    providerPhotos, linkedProviders: approved,
  };
});
