import { createTranslator, type MessageKey } from "../i18n/messages";
import { RoomRequestError } from "../rooms/client";
export const t = createTranslator("ru");
export function command() { return { request_id: crypto.randomUUID() }; }
export function label(id: string, name: string) { return name || t("social.person", {id: id.slice(0, 6)}); }
export function failure(cause: unknown) {
  if (cause instanceof RoomRequestError) {
    const code = cause.code;
    const keys = new Set(["AUTH_REQUIRED", "ACCESS_DENIED", "ROOM_NOT_FOUND", "WAIT_CAPACITY", "OTHER_MEETING", "TAB_LIMIT", "REALTIME_BUSY", "REALTIME_DISABLED", "JOIN_MEETING_REQUIRED", "NOTIFICATION_CONSENT", "RATE_LIMIT", "CHAT_LIMIT", "CURSOR_EXPIRED", "PROFILE_NOT_FOUND", "FRIEND_LIMIT", "FRIEND_STATE", "PROPOSAL_INVALID", "PROPOSAL_LIMIT", "INBOX_LIMIT"]);
    if (keys.has(code)) return t(`error.${code}` as MessageKey);
  }
  return t("error.UNAVAILABLE");
}
