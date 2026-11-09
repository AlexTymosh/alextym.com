/** Owns asynchronous Chat work across resets and component unmounts.
 * This is a local UI concurrency guard, not a server-side cancellation protocol.
 */
export type AssistantRequestLease = {
  signal: AbortSignal;
  isCurrent: () => boolean;
  finish: () => void;
};

export type HandoffActionLease = {
  isCurrent: () => boolean;
  finish: () => void;
};

export function createChatRequestLifecycle() {
  let sessionVersion = 0;
  let activeAssistant: AbortController | null = null;
  let activeHandoffAction: object | null = null;
  let handoffClosureRecorded = false;

  return {
    hasActiveAssistant(): boolean {
      return activeAssistant !== null && !activeAssistant.signal.aborted;
    },

    beginAssistantRequest(): AssistantRequestLease {
      activeAssistant?.abort();
      const controller = new AbortController();
      activeAssistant = controller;
      const version = sessionVersion;
      const isCurrent = () =>
        sessionVersion === version &&
        activeAssistant === controller &&
        !controller.signal.aborted;

      return {
        signal: controller.signal,
        isCurrent,
        finish: () => {
          if (isCurrent()) {
            activeAssistant = null;
          }
        },
      };
    },

    /** Serialize handoff POSTs synchronously, before a React re-render. */
    beginHandoffAction(): HandoffActionLease | null {
      if (activeHandoffAction !== null) {
        return null;
      }
      const token = {};
      const version = sessionVersion;
      activeHandoffAction = token;
      const isCurrent = () =>
        sessionVersion === version && activeHandoffAction === token;
      return {
        isCurrent,
        finish: () => {
          if (isCurrent()) {
            activeHandoffAction = null;
          }
        },
      };
    },

    /** A new server handoff can produce one terminal notice. */
    startHandoff(): void {
      handoffClosureRecorded = false;
    },

    /** SSE closure and POST /close may race; only the first reports closure. */
    claimHandoffClosed(): boolean {
      if (handoffClosureRecorded) {
        return false;
      }
      handoffClosureRecorded = true;
      return true;
    },

    captureSession(): () => boolean {
      const version = sessionVersion;
      return () => sessionVersion === version;
    },

    invalidate(): void {
      sessionVersion += 1;
      activeAssistant?.abort();
      activeAssistant = null;
      activeHandoffAction = null;
      handoffClosureRecorded = false;
    },
  };
}
