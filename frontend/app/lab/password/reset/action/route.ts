import { NextRequest, NextResponse } from "next/server";
import { FieldValue, getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid, isLabEnabled } from "../../../../../lib/portfolio-lab/firebase-server";
import { hasSameOrigin } from "../../../../../lib/portfolio-lab/session-origin";
import {
  completePasswordReset,
  eligibleForPasswordRecovery,
  type ResetCodeCheck,
  validNewPassword,
  validResetCode,
} from "../../../../../lib/portfolio-lab/password-recovery-policy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function reply(status: number, message: string) {
  return NextResponse.json({ message }, {
    status,
    headers: { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" },
  });
}

/** Only the pinned Firebase project API key is ever used; no caller-supplied URL. */
async function resetCodeRequest(apiKey: string, data: object): Promise<ResetCodeCheck | null> {
  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:resetPassword?key=${encodeURIComponent(apiKey)}`,
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
  if (!body || typeof body !== "object" || !("email" in body) ||
      !("requestType" in body) || typeof body.email !== "string" ||
      typeof body.requestType !== "string") return null;
  return { email: body.email, requestType: body.requestType };
}

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return reply(404, "Not found");
  if (!hasSameOrigin(request) || !request.headers.get("content-type")?.startsWith("application/json")) {
    return reply(403, "Invalid request origin");
  }
  if (Number(request.headers.get("content-length") || 0) > 10_000) {
    return reply(413, "Request too large");
  }
  let body: unknown;
  try {
    const reader = request.body?.getReader();
    if (!reader) return reply(400, "Invalid request");
    const decoder = new TextDecoder();
    let raw = "";
    let bytes = 0;
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > 10_000) {
        await reader.cancel();
        return reply(413, "Request too large");
      }
      raw += decoder.decode(chunk.value, { stream: true });
    }
    raw += decoder.decode();
    body = JSON.parse(raw);
  } catch {
    return reply(400, "Invalid request");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return reply(400, "Invalid request");
  }
  const payload = body as Record<string, unknown>;
  const oobCode = payload.oobCode;
  const newPassword = payload.newPassword;
  if (!validResetCode(oobCode) || !validNewPassword(newPassword)) {
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
    const result = await completePasswordReset({
      inspect: (code) => resetCodeRequest(apiKey, { oobCode: code }),
      confirm: (code, password) => resetCodeRequest(apiKey, { oobCode: code, newPassword: password }),
      lookupUser: async (email) => {
        const user = await auth.getUserByEmail(email);
        return { uid: user.uid, email: user.email || "", disabled: user.disabled };
      },
      loadRecord: async (uid) => {
        const snapshot = await db.collection("portfolio_lab_identities").doc(uid).get();
        return snapshot.exists ? snapshot.data() : null;
      },
      revoke: (uid) => auth.revokeRefreshTokens(uid),
      commit: async (uid) => {
        const identity = db.collection("portfolio_lab_identities").doc(uid);
        const event = db.collection("portfolio_lab_invitation_events").doc();
        await db.runTransaction(async (transaction) => {
          const snapshot = await transaction.get(identity);
          if (!eligibleForPasswordRecovery(
            uid, ownerUid, snapshot.exists ? snapshot.data() : null,
          )) throw new Error("Identity admission revoked during password reset");
          const now = Date.now();
          transaction.update(identity, {
            status: "active",
            password_state: "user_set",
            initial_password_expires_at_ms: FieldValue.delete(),
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
    }, oobCode, newPassword, ownerUid);
    if (result === "invalid") return reply(400, "Link invalid or expired; request a new one");
    return reply(200, "Password updated. Sign in using your new password.");
  } catch {
    // A consumed code plus a failed Firestore write is intentionally not
    // retried with stale data. Owner must issue a fresh code and reconcile.
    return reply(503, "Unable to finish safely; contact the Owner for a new link");
  }
}
