import { expect, test } from "@playwright/test";
import cases from "../../docs/contracts/portfolio-lab-admission-cases.json";
import { labAdmissionDecision, labSignInProvider } from "../lib/portfolio-lab/admission-policy";

test.describe("Portfolio Lab admission parity", () => {
  for (const entry of cases) {
    test(entry.name, () => {
      expect(
        labAdmissionDecision(
          entry.uid,
          entry.owner_uid,
          entry.provider,
          entry.record,
          entry.now_ms,
          entry.auth_time,
          entry.subject,
        ),
      ).toBe(entry.want);
    });
  }

  test("untrusted email is not a Firebase sign-in provider", () => {
    expect(labSignInProvider({ uid: "user" })).toBe("");
    expect(labSignInProvider({ firebase: { sign_in_provider: "password" } })).toBe("password");
  });
});
