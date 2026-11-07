import { submitEscalationClose } from "./escalation-api";

export type HandoffClose = (handoffId: string) => Promise<unknown>;

/**
 * Closing a local EventSource does not close its backend handoff session.
 * Best-effort cleanup intentionally has no callback into the reset chat UI.
 * A network failure may leave the session live until its server TTL expires.
 */
export async function closeDetachedHandoff(
  handoffId: string | null | undefined,
  close: HandoffClose = submitEscalationClose,
): Promise<boolean> {
  if (!handoffId) {
    return false;
  }

  try {
    await close(handoffId);
    return true;
  } catch {
    // A stale request must never show an error in a newer chat session.
    return false;
  }
}
