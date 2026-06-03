import type {
  ChatHistoryMessage,
  ChatResponse,
  ChatSource,
  Confidence,
  HandoffReason,
} from "../types/chat";

type SseEvent = {
  event: string;
  data: string;
};

type ChatStreamDone = {
  confidence: Confidence;
  not_enough_data: boolean;
  handoff_suggested?: boolean;
  handoff_reason?: HandoffReason | null;
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
    throw new Error("Streaming response unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() || "";

    for (const rawEvent of events) {
      handleSseEvent(parseSseEvent(rawEvent), { onToken, onSources, onDone });
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    handleSseEvent(parseSseEvent(buffer), { onToken, onSources, onDone });
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

  return (await response.json()) as ChatResponse;
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
): void {
  if (!sseEvent) {
    return;
  }

  const parsedPayload = safeParseJson(sseEvent.data);
  if (!isRecord(parsedPayload)) {
    return;
  }

  if (sseEvent.event === "token") {
    const token = parsedPayload.text;
    if (typeof token === "string") {
      handlers.onToken(token);
    }
    return;
  }

  if (sseEvent.event === "sources") {
    if (Array.isArray(parsedPayload.sources)) {
      handlers.onSources(parsedPayload.sources as ChatSource[]);
    }
    return;
  }

  if (sseEvent.event === "done") {
    const confidence = parseConfidence(parsedPayload.confidence);
    const handoffReason = parseHandoffReason(parsedPayload.handoff_reason);

    handlers.onDone({
      confidence,
      not_enough_data: parsedPayload.not_enough_data === true,
      handoff_suggested:
        typeof parsedPayload.handoff_suggested === "boolean"
          ? parsedPayload.handoff_suggested
          : undefined,
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

function parseHandoffReason(value: unknown): HandoffReason | null {
  if (
    value === "insufficient_data" ||
    value === "private_data" ||
    value === "language_unsupported" ||
    value === "user_requested_human"
  ) {
    return value;
  }
  return null;
}
