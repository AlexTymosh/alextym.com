import { useCallback, useEffect, useRef } from "react";

import {
  buildEscalationStreamUrl,
  closeEscalationStream as closeEscalationEventSource,
  parseEscalationStreamClosedReason,
  parseEscalationStreamMessage,
} from "../lib/escalation-api";
import type { EscalationStreamClosedReason } from "../types/chat";

type EscalationStreamAlexMessage = {
  id: string;
  content: string;
};

type UseEscalationStreamOptions = {
  onClosed: (reason: EscalationStreamClosedReason) => void;
  onError: () => void;
  onMessage: (message: EscalationStreamAlexMessage) => void;
  onMeta: () => void;
};

type UseEscalationStreamResult = {
  closeEscalationStream: () => void;
  openEscalationStream: (handoffId: string) => void;
  resetEscalationStream: () => void;
};

export function useEscalationStream({
  onClosed,
  onError,
  onMessage,
  onMeta,
}: UseEscalationStreamOptions): UseEscalationStreamResult {
  const eventSourceRef = useRef<EventSource | null>(null);
  const seenMessageIdsRef = useRef<Set<string>>(new Set());

  const closeEscalationStream = useCallback(() => {
    closeEscalationEventSource(eventSourceRef);
  }, []);

  const resetEscalationStream = useCallback(() => {
    closeEscalationStream();
    seenMessageIdsRef.current.clear();
  }, [closeEscalationStream]);

  const openEscalationStream = useCallback(
    (handoffId: string) => {
      closeEscalationStream();
      seenMessageIdsRef.current.clear();

      const eventSource = new EventSource(buildEscalationStreamUrl(handoffId));
      eventSourceRef.current = eventSource;

      eventSource.addEventListener("meta", () => {
        onMeta();
      });

      eventSource.addEventListener("message", (event) => {
        const message = parseEscalationStreamMessage(event);
        if (!message) {
          return;
        }

        if (seenMessageIdsRef.current.has(message.id)) {
          return;
        }
        seenMessageIdsRef.current.add(message.id);

        onMessage(message);
      });

      eventSource.addEventListener("closed", (event) => {
        const reason = parseEscalationStreamClosedReason(event);
        closeEscalationStream();
        onClosed(reason);
      });

      eventSource.addEventListener("error", () => {
        onError();
      });
    },
    [closeEscalationStream, onClosed, onError, onMessage, onMeta],
  );

  useEffect(() => {
    return closeEscalationStream;
  }, [closeEscalationStream]);

  return {
    closeEscalationStream,
    openEscalationStream,
    resetEscalationStream,
  };
}
