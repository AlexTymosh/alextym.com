export const ROOM_ROOT = "/portfolio/sameplace";
const slug = /^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$/;
const actions = new Set(["update", "design", "archive", "restore", "roles", "block", "remove", "unblock", "invite", "revoke_invite", "propose_transfer", "cancel_transfer", "accept_transfer"]);
export function roomOperation(method: string, parts: string[]): string | null {
  if (method === "GET" && parts.length === 1 && ["identity", "rooms"].includes(parts[0])) return parts[0];
  if (method === "POST" && parts.length === 1 && ["rooms", "redeem"].includes(parts[0])) return parts[0];
  if (method === "POST" && parts.length === 2 && parts[0] === "admin" && ["approval", "limits"].includes(parts[1])) return parts.join("/");
  if (parts[0] === "social" && parts.length === 2) {
    if (method === "GET" && parts[1] === "me") return parts.join("/");
    if (method === "POST" && ["profile", "friend", "read_notice"].includes(parts[1])) return parts.join("/");
    return null;
  }
  if (parts[0] !== "rooms" || !slug.test(parts[1] ?? "")) return null;
  if (method === "GET" && parts.length === 2) return parts.join("/");
  if (method === "GET" && parts.length === 3 && ["chat", "recipients", "decor"].includes(parts[2])) return parts.join("/");
  if (method === "POST" && parts.length === 3 && (actions.has(parts[2]) || ["favourite", "ping", "ticket"].includes(parts[2]))) return parts.join("/");
  if (method === "POST" && parts.length === 4 && parts[2] === "decor" && ["publish", "save_template", "delete_template", "music"].includes(parts[3])) return parts.join("/");
  if (method === "POST" && parts.length === 4 && ((parts[2] === "chat" && ["page", "send", "hide", "cleanup"].includes(parts[3])) || (parts[2] === "location" && ["propose", "answer", "cancel", "move"].includes(parts[3])))) return parts.join("/");
  return null;
}
export function validRoomSlug(value: string): boolean { return slug.test(value); }
export function validInviteToken(value: string): boolean { return /^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/.test(value); }
