import { expect, test } from "@playwright/test";
import { newLabIdentity } from "../lib/portfolio-lab/registration-policy";
import { labAdmissionDecision } from "../lib/portfolio-lab/admission-policy";

const timestamp = 1_800_000_000_000;

for (const provider of ["password", "google.com", "microsoft.com", "github.com", "facebook.com"]) {
  test(`first ${provider} sign-in creates account access without project rights`, () => {
    const claims = { uid: "new-user", firebase: {
      sign_in_provider: provider, identities: { [provider]: ["subject"] },
    } };
    const user = { uid: claims.uid, disabled: false, providerData: [{ providerId: provider, uid: "subject" }] };
    const record = newLabIdentity(claims, user, timestamp);
    expect(record?.status).toBe("active");
    expect(record).not.toHaveProperty("grants");
    expect(record).not.toHaveProperty("role");
    expect(labAdmissionDecision(claims.uid, "owner", provider, record, timestamp, undefined, "subject")).toBe("allowed");
  });
}

test("disabled, anonymous, mismatched UID and replaced provider subjects cannot register", () => {
  const claims = { uid: "user", firebase: { sign_in_provider: "google.com", identities: { "google.com": ["trusted"] } } };
  const user = { uid: "user", disabled: false, providerData: [{ providerId: "google.com", uid: "trusted" }] };
  expect(newLabIdentity(claims, { ...user, disabled: true }, timestamp)).toBeNull();
  expect(newLabIdentity(claims, { ...user, uid: "another" }, timestamp)).toBeNull();
  expect(newLabIdentity(claims, { ...user, providerData: [{ providerId: "google.com", uid: "other" }] }, timestamp)).toBeNull();
  expect(newLabIdentity({ uid: "user", firebase: { sign_in_provider: "anonymous" } }, user, timestamp)).toBeNull();
});
