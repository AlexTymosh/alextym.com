"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { OAuthProvider, reauthenticateWithPopup } from "firebase/auth";
import type { AccountProfile } from "../lib/portfolio-lab/account-profile";
import { labProviderNames } from "../lib/portfolio-lab/auth-ui";
import { getLabAuth } from "../lib/portfolio-lab/firebase-client";
import { useClientReady } from "../lib/use-client-ready";
import { AccountAvatar } from "./account-avatar";
import authStyles from "./lab-auth.module.css";
import styles from "./settings.module.css";

export function AccountProfileForm({ profile }: { profile: AccountProfile }) {
  const router = useRouter();
  const ready = useClientReady();
  const [firstName, setFirstName] = useState(profile.firstName);
  const [lastName, setLastName] = useState(profile.lastName);
  const [source, setSource] = useState(profile.avatarSource);
  const [image, setImage] = useState<string | null>(null);
  const [revision, setRevision] = useState(profile.revision);
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState(false);
  const imageSelection = useRef(0);
  const preview = source === "none" ? null : source === "upload" ? image || profile.avatarUrl
    : profile.providerPhotos.find((photo) => photo.provider === source)?.url
      || profile.providerPhotos[0]?.url || null;

  async function choosePhoto(file?: File) {
    const selection = ++imageSelection.current;
    setNotice("");
    if (!file) return;
    if (file.size > 2_000_000 || !["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      setFailed(true);
      setNotice("Choose a PNG, JPEG or WebP image smaller than 2 MB.");
      return;
    }
    setReading(true);
    const data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = reject;
      reader.readAsDataURL(file);
    }).catch(() => null);
    if (selection !== imageSelection.current) return;
    setReading(false);
    if (!data) {
      setFailed(true);
      setNotice("This image could not be read. Choose another file.");
      return;
    }
    setImage(data);
    setSource("upload");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch("/auth/profile", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ firstName, lastName, avatarSource: source, avatarData: image, revision }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Unable to save your profile.");
      setRevision(result.revision);
      setFailed(false);
      setNotice("Profile saved.");
      window.dispatchEvent(new Event("account-profile-updated"));
      router.refresh();
    } catch (error) {
      setFailed(true);
      setNotice(error instanceof Error ? error.message : "Unable to save your profile.");
    } finally {
      setBusy(false);
    }
  }

  async function importMicrosoftPhoto() {
    setBusy(true);
    setNotice("");
    const selection = ++imageSelection.current;
    try {
      const user = getLabAuth().currentUser;
      if (!user) throw new Error("Sign in again, then choose Use Microsoft photo.");
      const provider = new OAuthProvider("microsoft.com");
      provider.addScope("User.Read");
      const proof = await reauthenticateWithPopup(user, provider);
      const token = OAuthProvider.credentialFromResult(proof)?.accessToken;
      if (!token) throw new Error("Microsoft did not provide access to your photo. You can upload one instead.");
      const response = await fetch("https://graph.microsoft.com/v1.0/me/photo/$value", {
        headers: { Authorization: "Bearer " + token }, redirect: "error",
        signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) throw new Error("Your Microsoft photo is unavailable. You can upload one instead.");
      const blob = await response.blob();
      if (selection === imageSelection.current) {
        await choosePhoto(new File([blob], "microsoft-photo", { type: blob.type }));
      }
    } catch (error) {
      setFailed(true);
      setNotice(error instanceof Error && !(("code" in error))
        ? error.message : "Your Microsoft photo could not be imported. Try again or upload a photo.");
    } finally {
      setBusy(false);
    }
  }

  return <form className={styles.profileForm} onSubmit={(event) => void save(event)}>
    <div><h2>Profile</h2><p className={styles.description}>Your name and photo appear in your account menu.</p></div>
    <div className={styles.photo}>
      <AccountAvatar name={[firstName, lastName].join(" ").trim() || profile.email || "Account"} url={preview} size={84} />
      <div className={styles.photoActions}>
        <label htmlFor="account-photo">Profile photo</label>
        <input id="account-photo" className={styles.fileInput} type="file"
          accept="image/png,image/jpeg,image/webp" disabled={!ready || busy}
          onChange={(event) => void choosePhoto(event.target.files?.[0])} />
        <p className={authStyles.hint}>PNG, JPEG or WebP, up to 2 MB.</p>
      </div>
    </div>
    <div className={styles.photoChoices}>
      {profile.providerPhotos.map((photo) => <button key={photo.provider}
        className={authStyles.secondaryButton} type="button" disabled={!ready || busy}
        aria-pressed={source === photo.provider} onClick={() => { ++imageSelection.current; setReading(false); setSource(photo.provider); setImage(null); }}>
        Use {labProviderNames[photo.provider]} photo
      </button>)}
      {profile.linkedProviders.some((provider) => provider === "microsoft.com") &&
        !profile.providerPhotos.some((photo) => photo.provider === "microsoft.com") &&
        <button className={authStyles.secondaryButton} type="button" disabled={!ready || busy}
          onClick={() => void importMicrosoftPhoto()}>Use Microsoft photo</button>}
      {preview && <button className={authStyles.secondaryButton} type="button" disabled={!ready || busy}
        onClick={() => { ++imageSelection.current; setReading(false); setSource("none"); setImage(null); }}>Remove photo</button>}
    </div>
    <div className={styles.names}>
      <div className={authStyles.field}>
        <label htmlFor="first-name">First name</label>
        <input id="first-name" autoComplete="given-name" maxLength={80} value={firstName} disabled={!ready || busy}
          onChange={(event) => setFirstName(event.target.value)} />
      </div>
      <div className={authStyles.field}>
        <label htmlFor="last-name">Last name</label>
        <input id="last-name" autoComplete="family-name" maxLength={80} value={lastName} disabled={!ready || busy}
          onChange={(event) => setLastName(event.target.value)} />
      </div>
    </div>
    <div><p className={authStyles.hint}>Email</p><p className={styles.email}>{profile.email}</p></div>
    <button className={authStyles.primaryButton} type="submit" disabled={!ready || busy || reading}>{busy ? "Saving…" : "Save profile"}</button>
    {notice && <p className={authStyles.notice} role={failed ? "alert" : "status"}>{notice}</p>}
  </form>;
}
