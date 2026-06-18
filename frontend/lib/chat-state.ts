import {
  CHAT_HISTORY_ITEM_MAX_CHARS,
  CHAT_HISTORY_LIMIT,
  CHAT_HISTORY_TOTAL_MAX_CHARS,
  ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS,
  ESCALATION_TRANSCRIPT_LIMIT,
  ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS,
  HANDOFF_CONFIRMATION_PATTERNS,
  HANDOFF_REQUEST_PATTERNS,
  SCRIPTED_RESPONSE_DELAY_MS,
  chatShellCopy,
} from "../content/chat";
import type {
  ChatHistoryMessage,
  EscalationTranscriptMessage,
  HandoffState,
  Message,
} from "../types/chat";

const cyrillicHandoffInvitationMarkers = [
  "\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u043b \u0432\u0430\u0441 \u0441 \u0430\u043b\u0435\u043a\u0441\u043e\u043c",
  "\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u043b\u0438 \u0441 \u043d\u0438\u043c \u043b\u0438\u0447\u043d\u043e",
] as const;

export async function waitForScriptedResponse(
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Request aborted", "AbortError"));
      return;
    }

    const handleAbort = () => {
      window.clearTimeout(timeoutId);
      reject(new DOMException("Request aborted", "AbortError"));
    };

    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", handleAbort);
      resolve();
    }, SCRIPTED_RESPONSE_DELAY_MS);

    signal.addEventListener("abort", handleAbort, { once: true });
  });
}

export function chooseScriptedResponse(responses: readonly string[]): string {
  return (
    responses[Math.floor(Math.random() * responses.length)] ||
    responses[0] ||
    ""
  );
}

export function createMessageId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}`;
}

export function buildChatHistory(messages: Message[]): ChatHistoryMessage[] {
  const history: ChatHistoryMessage[] = [];
  let totalChars = 0;

  for (const message of [...messages].reverse()) {
    if (history.length >= CHAT_HISTORY_LIMIT) {
      break;
    }
    if (message.role === "alex") {
      continue;
    }

    const content = compactHistoryContent(message.text);
    if (!content) {
      continue;
    }

    if (totalChars + content.length > CHAT_HISTORY_TOTAL_MAX_CHARS) {
      break;
    }

    history.unshift({ role: message.role, content });
    totalChars += content.length;
  }

  return history;
}

export function compactHistoryContent(text: string): string {
  const compactText = text.replace(/\s+/g, " ").trim();
  return compactText.slice(0, CHAT_HISTORY_ITEM_MAX_CHARS);
}

export function buildEscalationTranscript(
  messages: Message[],
): EscalationTranscriptMessage[] {
  const transcript: EscalationTranscriptMessage[] = [];
  let totalChars = 0;

  for (const message of [...messages].reverse()) {
    if (transcript.length >= ESCALATION_TRANSCRIPT_LIMIT) {
      break;
    }
    if (message.role === "alex") {
      continue;
    }

    const content = message.text.replace(/\s+/g, " ").trim();
    if (!content) {
      continue;
    }

    const clippedContent = content.slice(
      0,
      ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS,
    );
    if (
      totalChars + clippedContent.length >
      ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS
    ) {
      break;
    }

    transcript.unshift({ role: message.role, content: clippedContent });
    totalChars += clippedContent.length;
  }

  return transcript;
}

export function isHumanHandoffActive(
  handoffId: string | null,
  state: HandoffState,
): boolean {
  return (
    Boolean(handoffId) &&
    ["waiting_for_alex", "connected", "error"].includes(state)
  );
}

export function shouldAssistantSuggestHandoff(message: Message): boolean {
  if (typeof message.handoffSuggested === "boolean") {
    return message.handoffSuggested;
  }

  return Boolean(message.notEnoughData || isHandoffInvitationText(message.text));
}

export function hasPendingHandoffSuggestion(messages: Message[]): boolean {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.text.trim());

  return Boolean(
    latestAssistantMessage && shouldAssistantSuggestHandoff(latestAssistantMessage),
  );
}

export function isHandoffInvitationText(text: string): boolean {
  const normalizedText = text.toLowerCase();
  const ownerHandoffMarkers = [
    chatShellCopy.handoffConnectLabel,
    chatShellCopy.handoffPromptAriaLabel,
    chatShellCopy.handoffPromptTitle,
  ].map((marker) => marker.toLowerCase());
  return (
    normalizedText.includes("would you like me to connect him directly") ||
    ownerHandoffMarkers.some((marker) => normalizedText.includes(marker)) ||
    normalizedText.includes("handoff prompt below") ||
    normalizedText.includes("offer a handoff") ||
    normalizedText.includes("website can offer a connection") ||
    cyrillicHandoffInvitationMarkers.some((marker) =>
      normalizedText.includes(marker),
    )
  );
}

export function isHandoffConfirmationText(text: string): boolean {
  const compactText = text.replace(/\s+/g, " ").trim();
  return HANDOFF_CONFIRMATION_PATTERNS.some((pattern) => pattern.test(compactText));
}

export function isHandoffRequestText(text: string): boolean {
  const compactText = text.replace(/\s+/g, " ").trim();
  return HANDOFF_REQUEST_PATTERNS.some((pattern) => pattern.test(compactText));
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
