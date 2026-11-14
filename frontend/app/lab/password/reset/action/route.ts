import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { FieldValue, getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid, isLabEnabled } from "../../../../../lib/portfolio-lab/firebase-server";
import { hasSameOrigin } from "../../../../../lib/portfolio-lab/session-origin";
import { hasLabJsonContent, readLabJson } from "../../../../../lib/portfolio-lab/request-json";
import {
  completePasswordReset,
  eligibleForPasswordRecovery,
  eligibleForPasswordCompletion,
  type ResetCodeCheck,
  validNewPassword,
  validResetCode,
  validResetUid,
} from "../../../../../lib/portfolio-lab/password-recovery-policy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function reply(status: number, message: string) {
  return NextResponse.json({ message }, {
    status,
    headers: { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" },
  });
}

/** Use the configured project API key for the fixed Identity Toolkit endpoint. */
async function resetCodeRequest(
  apiKey: string, data: object, confirmation = false,
): Promise<ResetCodeCheck | null> {
  // getLabAdminAuth() validates the local emulator configuration before this call.
  const emulatorHost = process.env.FIREBASE_AUTH_EMULATOR_HOST;
  const endpoint = emulatorHost
    ? `http://${emulatorHost}/identitytoolkit.googleapis.com`
    : "https://identitytoolkit.googleapis.com";
  const response = await fetch(
    `${endpoint}/v1/accounts:resetPassword?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(data),
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(12_000),
    },
  );
  // Invalid, consumed or expired codes do not reveal account existence.
  if (response.status === 400) return null;
  if (!response.ok) throw new Error("Identity provider unavailable");
  const body: unknown = await response.json();
  if (!body || typeof body !== "object" || !("email" in body) || typeof body.email !== "string") {
    return null;
  }
  const requestType = "requestType" in body
    ? body.requestType
    : confirmation ? "PASSWORD_RESET" : undefined;
  return typeof requestType === "string" ? { email: body.email, requestType } : null;
}

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return reply(404, "Not found");
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) {
    return reply(403, "Invalid request origin");
  }
  const body = await readLabJson(request, 10_000);
  if (body === "too_large") return reply(413, "Request too large");
  const uid = body?.uid;
  const oobCode = body?.oobCode;
  const newPassword = body?.newPassword;
  if (!validResetUid(uid) || !validResetCode(oobCode) || !validNewPassword(newPassword)) {
    return reply(400, "Invalid code or password");
  }

  const ownerUid = getOwnerUid();
  const projectId = process.env.FIREBASE_PROJECT_ID;
  const clientProjectId = process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID;
  const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  if (!ownerUid || !projectId || projectId !== clientProjectId || !apiKey) {
    return reply(503, "Password recovery unavailable");
  }

  try {
    const auth = getLabAdminAuth();
    const db = getFirestore(auth.app);
    const digest = createHash("sha256").update(oobCode).digest();
    const codeMatches = (record: unknown) => {
      const stored = (record as { password_setup_code_digest?: unknown } | null)
        ?.password_setup_code_digest;
      return typeof stored === "string" && /^[a-f0-9]{64}$/.test(stored) &&
        timingSafeEqual(digest, Buffer.from(stored, "hex"));
    };
    const result = await completePasswordReset({
      inspect: (code) => resetCodeRequest(apiKey, { oobCode: code }),
      confirm: (code, password) => resetCodeRequest(
        apiKey, { oobCode: code, newPassword: password }, true,
      ),
      lookupUser: async (uid) => {
        try {
          const user = await auth.getUser(uid);
          return { uid: user.uid, email: user.email || "", disabled: user.disabled };
        } catch (error) {
          if ((error as { code?: string }).code === "auth/user-not-found") return null;
          throw error;
        }
      },
      loadRecord: async (uid) => {
        const snapshot = await db.collection("portfolio_lab_identities").doc(uid).get();
        return snapshot.exists ? snapshot.data() : null;
      },
      codeMatches,
      begin: async (uid) => {
        const identity = db.collection("portfolio_lab_identities").doc(uid);
        const event = db.collection("portfolio_lab_invitation_events").doc();
        return db.runTransaction(async (transaction) => {
          const snapshot = await transaction.get(identity);
          const record = snapshot.data();
          if (!eligibleForPasswordRecovery(
            uid, ownerUid, record,
          ) || !codeMatches(record)) return null;
          const now = Date.now();
          // Lock password-based admission BEFORE the Firebase password changes.
          transaction.update(identity, {
            password_state: "reset_pending",
            password_reset_started_at_ms: now,
            password_reset_operation_id: event.id,
            password_setup_code_digest: FieldValue.delete(),
          });
          transaction.create(event, {
            schema_version: 1,
            uid,
            action: "password_reset_started",
            created_at_ms: now,
          });
          return event.id;
        });
      },
      revoke: (uid) => auth.revokeRefreshTokens(uid),
      commit: async (uid, operationId) => {
        const identity = db.collection("portfolio_lab_identities").doc(uid);
        const event = db.collection("portfolio_lab_invitation_events").doc();
        await db.runTransaction(async (transaction) => {
          const snapshot = await transaction.get(identity);
          if (!eligibleForPasswordCompletion(
            uid, ownerUid, snapshot.exists ? snapshot.data() : null, operationId,
          )) throw new Error("Password reset state changed during confirmation");
          const now = Date.now();
          transaction.update(identity, {
            status: "active",
            password_state: "user_set",
            initial_password_expires_at_ms: FieldValue.delete(),
            password_reset_started_at_ms: FieldValue.delete(),
            password_reset_operation_id: FieldValue.delete(),
            password_changed_at_ms: now,
          });
          transaction.create(event, {
            schema_version: 1,
            uid,
            action: "password_reset_code_redeemed",
            created_at_ms: now,
          });
        });
      },
    }, uid, oobCode, newPassword, ownerUid);
    if (result === "invalid") return reply(400, "Link invalid or expired; request a new one");
    return reply(200, "Password updated. Sign in using your new password.");
  } catch {
    // A consumed code or interrupted confirmation leaves reset_pending.
    // Only an audited Owner operation can repair this fail-closed state.
    return reply(503, "Unable to finish safely; contact the Owner for a new link");
  }
}
