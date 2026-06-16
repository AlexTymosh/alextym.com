import type {
  EscalationCloseResponse,
  EscalationMessageResponse,
  EscalationResponse,
  EscalationStreamMessage,
  EscalationTranscriptMessage,
  HandoffState,
} from "../types/chat";
import { createMessageId } from "./chat-state";

const BROWSER_BACKEND_ORIGIN =
  process.env.NEXT_PUBLIC_BACKEND_ORIGIN?.replace(/\/$/, "") ?? "";

export class EscalationApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly contactPath: string | null;

  constructor({
    status,
    message,
    code = null,
    contactPath = null,
  }: {
    status: number;
    message: string;
    code?: string | null;
    contactPath?: string | null;
  }) {
    super(message);
    this.name = "EscalationApiError";
    this.status = status;
    this.code = code;
    this.contactPath = contactPath;
  }
}

export function isHandoffUnavailableError(
  error: unknown,
): error is EscalationApiError {
  return (
    error instanceof EscalationApiError &&
    error.code === "handoff_outside_hours"
  );
}

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
    throw await buildEscalationApiError(
      response,
      "Escalation request unavailable.",
    );
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
    throw await buildEscalationApiError(
      response,
      "Escalation message request unavailable.",
    );
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
    throw await buildEscalationApiError(
      response,
      "Escalation close request unavailable.",
    );
  }

  return (await response.json()) as EscalationCloseResponse;
}

export function buildEscalationStreamUrl(handoffId: string): string {
  const streamPath = `/api/escalations/${encodeURIComponent(handoffId)}/stream`;
  return BROWSER_BACKEND_ORIGIN ? `${BROWSER_BACKEND_ORIGIN}${streamPath}` : streamPath;
}

export function parseEscalationStreamMessage(
  event: Event,
): { id: string; content: string } | null {
  if (!(event instanceof MessageEvent)) {
    return null;
  }

  const payload = safeParseJson(event.data) as EscalationStreamMessage | null;
  if (!payload) {
    return null;
  }

  const role = typeof payload.role === "string" ? payload.role.toLowerCase() : "";
  if (role === "user" || role === "visitor") {
    return null;
  }

  const content = typeof payload.content === "string" ? payload.content : "";
  if (!content.trim()) {
    return null;
  }

  const id =
    typeof payload.id === "string" && payload.id
      ? payload.id
      : createMessageId("alex");

  return { id, content };
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

async function buildEscalationApiError(
  response: Response,
  fallbackMessage: string,
): Promise<EscalationApiError> {
  const payload = await safeReadJson(response);
  const detail = asRecord(payload?.detail);
  const message = getString(detail?.message) || getString(payload?.detail);

  return new EscalationApiError({
    status: response.status,
    message: message || fallbackMessage,
    code: getString(detail?.code),
    contactPath: getString(detail?.contact_path),
  });
}

async function safeReadJson(
  response: Response,
): Promise<Record<string, unknown> | null> {
  try {
    const payload = (await response.json()) as unknown;
    return asRecord(payload);
  } catch {
    return null;
  }
}

function safeParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}
