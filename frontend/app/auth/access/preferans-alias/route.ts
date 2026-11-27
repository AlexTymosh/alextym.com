import { NextRequest, NextResponse } from "next/server";
import { getFirestore } from "firebase-admin/firestore";
import { getLabAdminAuth, getOwnerUid, isLabEnabled, LAB_SESSION_COOKIE } from "../../../../lib/portfolio-lab/firebase-server";
import { labSession } from "../../../../lib/portfolio-lab/project-access-server";
import { isRecentLabLogin } from "../../../../lib/portfolio-lab/session-policy";
import { hasSameOrigin } from "../../../../lib/portfolio-lab/session-origin";
import { hasLabJsonContent, readLabJson } from "../../../../lib/portfolio-lab/request-json";
import { aliasChange } from "../../../../lib/portfolio-lab/preferans-alias";
import { firebaseQuota } from "../../../../lib/portfolio-lab/firestore-quota";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const reply = (status:number, data:object={}) => NextResponse.json(data,{status,headers:{"Cache-Control":"no-store"}});

export async function POST(request:NextRequest) {
  if (!isLabEnabled()) return reply(404);
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) return reply(403);
  try {
    const session = await labSession(request.cookies.get(LAB_SESSION_COOKIE)?.value);
    if (!session) return reply(401);
    if (session.uid !== getOwnerUid()) return reply(403);
    if (!isRecentLabLogin(session.auth_time)) return reply(403,{code:"RECENT_LOGIN_REQUIRED"});
    const body = await readLabJson(request,2048);
    if (body === "too_large") return reply(413);
    const change = aliasChange(body);
    if (!change) return reply(400);
    const auth = await getLabAdminAuth();
    const account = await auth.getUser(change.uid);
    if (account.disabled) return reply(409);
    const db = getFirestore(auth.app);
    const identity = db.collection("portfolio_lab_identities").doc(change.uid);
    const profile = db.collection("portfolio_lab_profiles").doc(change.uid);
    const status = await firebaseQuota.run(() => db.runTransaction(async tx => {
      const record = (await tx.get(identity)).data();
      if (change.uid !== session.uid && (record?.schema_version !== 1 || record.uid !== change.uid || record.status !== "active")) return 409;
      tx.set(profile,{preferans_alias:change.alias},{merge:true});
      return 200;
    }));
    return reply(status,status===200?{alias:change.alias}:{});
  } catch { return reply(503); }
}
