import type { AssistantMessage, HandoffState, Message } from "../types/chat";

export function getHandoffContactPath(contactPath: string | null): string {
  const fallback = "/contact";
  const path = contactPath?.trim();
  if (
    !path?.startsWith("/") ||
    path.startsWith("//") ||
    path.includes("\\") ||
    Array.from(path).some(
      (char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127,
    )
  ) {
    return fallback;
  }

  try {
    // Reject malformed escapes and normalize dot segments before rendering href.
    decodeURI(path);
    const base = "https://handoff.invalid";
    const url = new URL(path, base);
    if (url.origin !== base || url.pathname.startsWith("//")) {
      return fallback;
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
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

export function getPendingHandoffSuggestion(
  messages: Message[],
): AssistantMessage | null {
  const latestAssistantMessage = [...messages]
    .reverse()
    .find(
      (message): message is AssistantMessage =>
        message.role === "assistant" && Boolean(message.text.trim()),
    );

  return latestAssistantMessage?.handoffSuggested
    ? latestAssistantMessage
    : null;
}
