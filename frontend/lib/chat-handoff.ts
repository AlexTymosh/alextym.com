import {
  HANDOFF_CONFIRMATION_PATTERNS,
  HANDOFF_REQUEST_PATTERNS,
  chatShellCopy,
} from "../content/chat";
import type { HandoffState, Message } from "../types/chat";

const cyrillicHandoffInvitationMarkers = [
  "\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u043b \u0432\u0430\u0441 \u0441 \u0430\u043b\u0435\u043a\u0441\u043e\u043c",
  "\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u043b\u0438 \u0441 \u043d\u0438\u043c \u043b\u0438\u0447\u043d\u043e",
] as const;

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
