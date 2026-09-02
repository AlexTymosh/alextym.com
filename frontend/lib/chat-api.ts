import type {
  ChatHistoryMessage,
  ChatResponse,
  ChatSource,
  Confidence,
  HandoffReason,
  RetrievalStatus,
} from "../types/chat";

type SseEvent = {
  event: string;
  data: string;
};

export type ChatStreamFailureKind =
  | "backend_error"
  | "incomplete"
  | "unavailable";

export class ChatStreamError extends Error {
  readonly kind: ChatStreamFailureKind;

  constructor(kind: ChatStreamFailureKind, message: string) {
    super(message);
    this.name = "ChatStreamError";
    this.kind = kind;
    Object.setPrototypeOf(this, ChatStreamError.prototype);
  }
}

export function isChatStreamError(error: unknown): error is ChatStreamError {
  return error instanceof ChatStreamError;
}

type ChatStreamDone = {
  confidence: Confidence;
  not_enough_data: boolean;
  retrieval_status: RetrievalStatus;
  handoff_suggested: boolean;
  handoff_reason: HandoffReason | null;
  language_unsupported?: boolean;
  user_requested_human?: boolean;
};

type StreamChatResponseOptions = {
  message: string;
  history: ChatHistoryMessage[];
  signal: AbortSignal;
  onToken: (token: string) => void;
  onSources: (sources: ChatSource[]) => void;
  onDone: (done: ChatStreamDone) => void;
};

const STREAM_UNAVAILABLE_MESSAGE = "Streaming response unavailable.";
const STREAM_INCOMPLETE_MESSAGE =
  "The streaming response ended before completion.";
const STREAM_BACKEND_ERROR_MESSAGE =
  "Something went wrong. Please try again later.";

export async function streamChatResponse({
  message,
  history,
  signal,
  onToken,
  onSources,
  onDone,
}: StreamChatResponseOptions): Promise<void> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new ChatStreamError("unavailable", STREAM_UNAVAILABLE_MESSAGE);
  }

  if (!isSseResponse(response)) {
    throw new ChatStreamError("unavailable", STREAM_UNAVAILABLE_MESSAGE);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receivedDone = false;

  try {
    while (!receivedDone) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || "";

      for (const rawEvent of events) {
        receivedDone =
          handleSseEvent(parseSseEvent(rawEvent), {
            onToken,
            onSources,
            onDone,
          }) === "done";

        if (receivedDone) {
          await cancelReader(reader);
          break;
        }
      }
    }

    if (!receivedDone) {
      buffer += decoder.decode();
      if (buffer.trim()) {
        receivedDone =
          handleSseEvent(parseSseEvent(buffer), {
            onToken,
            onSources,
            onDone,
          }) === "done";
      }
    }
  } finally {
    reader.releaseLock();
  }

  if (!receivedDone) {
    throw new ChatStreamError("incomplete", STREAM_INCOMPLETE_MESSAGE);
  }
}

export async function fetchJsonChatResponse(
  message: string,
  history: ChatHistoryMessage[],
  signal: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!response.ok) {
    throw new Error("JSON fallback response unavailable.");
  }

  const payload = (await response.json()) as ChatResponse;
  return {
    ...payload,
    handoff_suggested: payload.handoff_suggested === true,
    handoff_reason: parseHandoffReason(payload.handoff_reason),
  };
}

function parseSseEvent(rawEvent: string): SseEvent | null {
  const lines = rawEvent.split(/\r?\n/);
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!dataLines.length) {
    return null;
  }

  return { event, data: dataLines.join("\n") };
}

function handleSseEvent(
  sseEvent: SseEvent | null,
  handlers: {
    onToken: (token: string) => void;
    onSources: (sources: ChatSource[]) => void;
    onDone: (done: ChatStreamDone) => void;
  },
): "continue" | "done" {
  if (!sseEvent) {
    return "continue";
  }

  if (sseEvent.event === "error") {
    const parsedErrorPayload = safeParseJson(sseEvent.data);
    const message =
      isRecord(parsedErrorPayload) && typeof parsedErrorPayload.message === "string"
        ? parsedErrorPayload.message
        : STREAM_BACKEND_ERROR_MESSAGE;

    throw new ChatStreamError("backend_error", message);
  }

  const parsedPayload = safeParseJson(sseEvent.data);
  if (!isRecord(parsedPayload)) {
    return "continue";
  }

  if (sseEvent.event === "token") {
    const token = parsedPayload.text;
    if (typeof token === "string") {
      handlers.onToken(token);
    }
    return "continue";
  }

  if (sseEvent.event === "sources") {
    if (Array.isArray(parsedPayload.sources)) {
      handlers.onSources(parsedPayload.sources as ChatSource[]);
    }
    return "continue";
  }

  if (sseEvent.event === "done") {
    const confidence = parseConfidence(parsedPayload.confidence);
    const handoffReason = parseHandoffReason(parsedPayload.handoff_reason);

    handlers.onDone({
      confidence,
      not_enough_data: parsedPayload.not_enough_data === true,
      retrieval_status: parseRetrievalStatus(parsedPayload.retrieval_status),
      handoff_suggested: parsedPayload.handoff_suggested === true,
      handoff_reason: handoffReason,
      language_unsupported:
        typeof parsedPayload.language_unsupported === "boolean"
          ? parsedPayload.language_unsupported
          : undefined,
      user_requested_human:
        typeof parsedPayload.user_requested_human === "boolean"
          ? parsedPayload.user_requested_human
          : undefined,
    });
    return "done";
  }

  return "continue";
}

function isSseResponse(response: Response): boolean {
  const contentType = response.headers.get("content-type") || "";
  return contentType.toLowerCase().startsWith("text/event-stream");
}

async function cancelReader(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): Promise<void> {
  try {
    await reader.cancel();
  } catch {
    // The stream may already be closed by the server after the terminal event.
  }
}

function safeParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseConfidence(value: unknown): Confidence {
  if (value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "low";
}

function parseRetrievalStatus(value: unknown): RetrievalStatus {
  if (
    value === "success" ||
    value === "empty" ||
    value === "unavailable" ||
    value === "not_requested"
  ) {
    return value;
  }
  return "not_requested";
}

function parseHandoffReason(value: unknown): HandoffReason | null {
  if (
    value === "insufficient_data" ||
    value === "private_data" ||
    value === "language_unsupported" ||
    value === "user_requested_human" ||
    value === "availability_or_contact" ||
    value === "service_enquiry" ||
    value === "public_boundary"
  ) {
    return value;
  }
  return null;
}
