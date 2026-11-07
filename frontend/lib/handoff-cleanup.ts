import { purgeEscalationSession } from "./escalation-api";

export type HandoffPurge = (handoffId: string) => Promise<unknown>;

/**
 * Reset discards the server-side Redis transcript, unlike manual close.
 * Best-effort cleanup intentionally has no callback into the reset chat UI.
 * A network failure can leave the session until its TTL; Telegram copies
 * already delivered to the operator are outside this Redis purge.
 */
export async function purgeDetachedHandoff(
  handoffId: string | null | undefined,
  purge: HandoffPurge = purgeEscalationSession,
): Promise<boolean> {
  if (!handoffId) {
    return false;
  }

  try {
    await purge(handoffId);
    return true;
  } catch {
    // A stale request must never show an error in a newer chat session.
    return false;
  }
}
