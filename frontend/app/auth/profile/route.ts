import { NextRequest, NextResponse } from "next/server";
import { getFirestore } from "firebase-admin/firestore";
import sharp from "sharp";
import { getAccountProfile } from "../../../lib/portfolio-lab/account-profile-server";
import { validProfileName } from "../../../lib/portfolio-lab/account-profile";
import { getLabAdminAuth, getOwnerUid, isLabEnabled } from "../../../lib/portfolio-lab/firebase-server";
import { currentLabSession } from "../../../lib/portfolio-lab/project-access-server";
import { decideLabAdmission } from "../../../lib/portfolio-lab/lab-admission-server";
import { hasSameOrigin } from "../../../lib/portfolio-lab/session-origin";
import { hasLabJsonContent, readLabJson } from "../../../lib/portfolio-lab/request-json";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const reply = (data: object, status = 200) =>
  NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });

export async function GET() {
  if (!isLabEnabled()) return reply({ error: "Not found" }, 404);
  try {
    const session = await currentLabSession();
    if (!session) return reply({ error: "Sign in required" }, 401);
    return reply(await getAccountProfile(session.uid));
  } catch {
    return reply({ error: "Profile unavailable" }, 503);
  }
}

async function avatarImage(value: unknown): Promise<string> {
  if (typeof value !== "string" || value.length > 2_800_000 ||
      !/^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value)) {
    throw new Error("Invalid image");
  }
  const input = Buffer.from(value.slice(value.indexOf(",") + 1), "base64");
  const image = sharp(input, { limitInputPixels: 16_000_000, animated: false });
  const metadata = await image.metadata();
  if (!["png", "jpeg", "webp"].includes(metadata.format || "")) throw new Error("Unsupported image");
  const output = await image.rotate().resize(256, 256, { fit: "cover" }).webp({ quality: 78 }).toBuffer();
  if (output.byteLength > 100_000) throw new Error("Image too large");
  return "data:image/webp;base64," + output.toString("base64");
}

export async function POST(request: NextRequest) {
  if (!isLabEnabled()) return reply({ error: "Not found" }, 404);
  if (!hasSameOrigin(request) || !hasLabJsonContent(request)) return reply({ error: "Invalid request" }, 403);
  try {
    const session = await currentLabSession();
    if (!session) return reply({ error: "Sign in required" }, 401);
    const body = await readLabJson(request, 3_000_000);
    if (body === "too_large") return reply({ error: "Image must be smaller than 2 MB" }, 413);
    if (!body || !validProfileName(body.firstName) || !validProfileName(body.lastName) ||
        !Number.isSafeInteger(body.revision) || (body.revision as number) < 0) {
      return reply({ error: "Enter names of up to 80 characters" }, 400);
    }
    const profile = await getAccountProfile(session.uid);
    const firstName = body.firstName.trim();
    const lastName = body.lastName.trim();
    const source = body.avatarSource;
    if (source !== "account" && source !== "none" && source !== "upload" &&
        !profile.providerPhotos.some((photo) => photo.provider === source)) {
      return reply({ error: "Choose an available account photo" }, 400);
    }
    let uploaded: string | null = null;
    if (source === "upload" && body.avatarData) {
      try { uploaded = await avatarImage(body.avatarData); }
      catch { return reply({ error: "Choose a PNG, JPEG or WebP image smaller than 2 MB" }, 400); }
    }
    if (source === "upload" && !uploaded && profile.avatarSource !== "upload") {
      return reply({ error: "Choose an image to upload" }, 400);
    }
    const auth = await getLabAdminAuth();
    const db = getFirestore(auth.app);
    const ref = db.collection("portfolio_lab_profiles").doc(session.uid);
    const identity = db.collection("portfolio_lab_identities").doc(session.uid);
    const status = await db.runTransaction(async (transaction) => {
      const [stored, admission] = await transaction.getAll(ref, identity);
      if (decideLabAdmission(session, getOwnerUid(), admission.data()) !== "allowed") return 403;
      const current = stored.data();
      if ((current?.revision ?? 0) !== body.revision) return 409;
      transaction.set(ref, {
        first_name: firstName, last_name: lastName,
        avatar_source: source,
        avatar_data_url: source === "upload" ? (uploaded || current?.avatar_data_url || null) : null,
        revision: (body.revision as number) + 1, updated_at_ms: Date.now(),
      });
      return 200;
    });
    return status === 200 ? reply({ ok: true, revision: (body.revision as number) + 1 })
      : reply({ error: status === 409 ? "Profile changed. Reload before saving again." : "Sign in again to update your profile." }, status);
  } catch {
    return reply({ error: "Unable to save your profile. Try again." }, 503);
  }
}
