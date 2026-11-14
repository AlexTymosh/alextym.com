import { expect, test } from "@playwright/test";
import {
  completePasswordReset,
  eligibleForPasswordRecovery,
  eligibleForPasswordCompletion,
  validNewPassword,
  validResetCode,
  type PasswordResetEffects,
} from "../lib/portfolio-lab/password-recovery-policy";

const code = "abcdefghijklmn0123456789";
const password = "safe-new-password-123";
const record = { schema_version: 1, uid: "test-uid", status: "invited", password_state: "none" };

function harness() {
  const calls: string[] = [];
  const effects: PasswordResetEffects = {
    inspect: async () => { calls.push("inspect"); return { email: "user@example.test", requestType: "PASSWORD_RESET" }; },
    lookupUser: async () => { calls.push("lookup"); return { uid: "test-uid", email: "user@example.test", disabled: false }; },
    loadRecord: async () => { calls.push("record"); return record; },
    codeMatches: () => true,
    begin: async () => { calls.push("begin"); return "test-operation"; },
    confirm: async () => { calls.push("confirm"); return { email: "user@example.test", requestType: "PASSWORD_RESET" }; },
    revoke: async () => { calls.push("revoke"); },
    commit: async () => { calls.push("commit"); },
  };
  return { calls, effects };
}

test.describe("Portfolio Lab password recovery contract", () => {
  test("accepts valid reset links and rejects malformed codes", () => {
    expect(validResetCode(code)).toBe(true);
    for (const value of [null, "", "short", "bad code", "x".repeat(5000)]) {
      expect(validResetCode(value)).toBe(false);
    }
  });

  test("enforces the application password length and control rules", () => {
    expect(validNewPassword(password)).toBe(true);
    for (const value of [null, "short", "a".repeat(129), "12-valid-characters\n"]) {
      expect(validNewPassword(value)).toBe(false);
    }
  });

  test("only invited or active, pinned non-owner UIDs can complete setup", () => {
    expect(eligibleForPasswordRecovery("test-uid", "owner", record)).toBe(true);
    expect(eligibleForPasswordRecovery("owner", "owner", record)).toBe(false);
    expect(eligibleForPasswordRecovery("test-uid", "owner", { ...record, status: "revoked" })).toBe(false);
    expect(eligibleForPasswordRecovery("test-uid", "owner", { ...record, status: "disabled" })).toBe(false);
    expect(eligibleForPasswordRecovery("other", "owner", record)).toBe(false);
    expect(eligibleForPasswordRecovery("test-uid", "owner", null)).toBe(false);
  });

  test("reconciles only after real provider code redemption and token revocation", async () => {
    const { effects, calls } = harness();
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("success");
    expect(calls).toEqual(["record", "inspect", "lookup", "begin", "confirm", "lookup", "revoke", "commit"]);
  });

  test("invalid code cannot trigger a provider mutation", async () => {
    const { effects, calls } = harness();
    expect(await completePasswordReset(effects, "test-uid", "x", password, "owner")).toBe("invalid");
    expect(calls).toEqual([]);
  });

  test("unknown or expired provider code cannot reach a password update", async () => {
    const { effects, calls } = harness();
    effects.inspect = async () => { calls.push("inspect"); return null; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toEqual(["record", "inspect"]);
  });

  test("a provider code without an Owner link never reaches Firebase", async () => {
    const { effects, calls } = harness();
    effects.codeMatches = () => false;
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toEqual(["record"]);
  });

  test("a concurrent redemption that loses the transaction does not change the password", async () => {
    const { effects, calls } = harness();
    effects.begin = async () => { calls.push("begin"); return null; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toEqual(["record", "inspect", "lookup", "begin"]);
  });

  test("only PASSWORD_RESET action codes are accepted", async () => {
    const { effects, calls } = harness();
    effects.inspect = async () => { calls.push("inspect"); return { email: "user@example.test", requestType: "VERIFY_EMAIL" }; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toEqual(["record", "inspect"]);
  });

  test("revoked Firestore identity cannot consume code through application", async () => {
    const { effects, calls } = harness();
    effects.loadRecord = async () => { calls.push("record"); return { ...record, status: "revoked" }; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toEqual(["record"]);
  });

  test("mismatched provider confirmation cannot mark password user-set", async () => {
    const { effects, calls } = harness();
    effects.confirm = async () => { calls.push("confirm"); return { email: "other@example.test", requestType: "PASSWORD_RESET" }; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toContain("begin");
    expect(calls).not.toContain("revoke");
    expect(calls).not.toContain("commit");
  });

  test("Firebase UID rotation during reset fails closed", async () => {
    const { effects, calls } = harness();
    let num = 0;
    effects.lookupUser = async () => { calls.push("lookup"); num++; return { uid: num === 1 ? "test-uid" : "other", email: "user@example.test", disabled: false }; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).not.toContain("revoke");
    expect(calls).not.toContain("commit");
  });

  test("failed revocation cannot enable password admission", async () => {
    const { effects, calls } = harness();
    effects.revoke = async () => { calls.push("revoke"); throw new Error("transient"); };
    await expect(completePasswordReset(effects, "test-uid", code, password, "owner")).rejects.toThrow();
    expect(calls).not.toContain("commit");
  });

  test("failed begin prevents all Firebase password mutations", async () => {
    const { effects, calls } = harness();
    effects.begin = async () => { calls.push("begin"); throw new Error("Firestore unavailable"); };
    await expect(completePasswordReset(effects, "test-uid", code, password, "owner")).rejects.toThrow();
    expect(calls).toEqual(["record", "inspect", "lookup", "begin"]);
  });

  test("provider failure after begin leaves password admission locked", async () => {
    const { effects, calls } = harness();
    effects.confirm = async () => { calls.push("confirm"); return null; };
    expect(await completePasswordReset(effects, "test-uid", code, password, "owner")).toBe("invalid");
    expect(calls).toContain("begin");
    expect(calls).not.toContain("commit");
  });

  test("completion requires the distinct reset_pending state", () => {
    const pending = { ...record, password_state: "reset_pending", password_reset_operation_id: "test-operation" };
    expect(eligibleForPasswordCompletion("test-uid", "owner", pending, "test-operation")).toBe(true);
    expect(eligibleForPasswordCompletion("test-uid", "owner", pending, "stale-operation")).toBe(false);
    expect(eligibleForPasswordRecovery("test-uid", "owner", pending)).toBe(false);
    expect(eligibleForPasswordCompletion("test-uid", "owner", record, "test-operation")).toBe(false);
    expect(eligibleForPasswordCompletion("test-uid", "owner", { ...pending, status: "revoked" }, "test-operation")).toBe(false);
    expect(eligibleForPasswordCompletion("other-uid", "owner", pending, "test-operation")).toBe(false);
  });

  test("failed transactional update surfaces explicit recovery", async () => {
    const { effects, calls } = harness();
    effects.commit = async () => { calls.push("commit"); throw new Error("transaction failed"); };
    await expect(completePasswordReset(effects, "test-uid", code, password, "owner")).rejects.toThrow();
    expect(calls).toContain("revoke");
  });
});
