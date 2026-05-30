import type {
  EscalationCloseResponse,
  EscalationMessageResponse,
  EscalationResponse,
  EscalationStreamMessage,
  EscalationTranscriptMessage,
  HandoffState,
} from "../types/chat";
import { createMessageId } from "./chat-state";

export async function submitEscalation(
  transcript: EscalationTranscriptMessage[],
): Promise<EscalationResponse> {
  const response = await fetch("/api/escalations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      consent_accepted: true,
      reason: "user_requested_human",
      transcript,
      company_website: "",
    }),
  });

  if (!response.ok) {
    throw new Error("Escalation request unavailable.");
  }

  return (await response.json()) as EscalationResponse;
}

export async function submitEscalationMessage(
  handoffId: string,
  content: string,
): Promise<EscalationMessageResponse> {
  const response = await fetch(
    `/api/escalations/${encodeURIComponent(handoffId)}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        content,
        company_website: "",
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Escalation message request unavailable.");
  }

  return (await response.json()) as EscalationMessageResponse;
}

export async function submitEscalationClose(
  handoffId: string,
): Promise<EscalationCloseResponse> {
  const response = await fetch(
    `/api/escalations/${encodeURIComponent(handoffId)}/close`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error("Escalation close request unavailable.");
  }

  return (await response.json()) as EscalationCloseResponse;
}

export function parseEscalationStreamMessage(
  event: Event,
): { id: string; content: string } | null {
  if (!(event instanceof MessageEvent)) {
    return null;
  }

  const payload = safeParseJson(event.data) as EscalationStreamMessage | null;
  if (!payload || payload.role !== "alex") {
    return null;
  }

  const content = typeof payload.content === "string" ? payload.content : "";
  if (!content.trim()) {
    return null;
  }

  const id = typeof payload.id === "string" && payload.id
    ? payload.id
    : createMessageId("alex");

  return { id, content };
}

function safeParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export function normaliseHandoffState(
  state: string | null | undefined,
): HandoffState {
  if (state === "connected") {
    return "connected";
  }
  if (state === "closed") {
    return "closed";
  }
  return "waiting_for_alex";
}

export function closeEscalationStream(eventSourceRef: {
  current: EventSource | null;
}): void {
  eventSourceRef.current?.close();
  eventSourceRef.current = null;
}
