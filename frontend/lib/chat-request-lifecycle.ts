/** Owns asynchronous Chat work across resets and component unmounts.
 * This is a local UI concurrency guard, not a server-side cancellation protocol.
 */
export type AssistantRequestLease = {
  signal: AbortSignal;
  isCurrent: () => boolean;
  finish: () => void;
};

export function createChatRequestLifecycle() {
  let sessionVersion = 0;
  let activeAssistant: AbortController | null = null;

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

    captureSession(): () => boolean {
      const version = sessionVersion;
      return () => sessionVersion === version;
    },

    invalidate(): void {
      sessionVersion += 1;
      activeAssistant?.abort();
      activeAssistant = null;
    },
  };
}
