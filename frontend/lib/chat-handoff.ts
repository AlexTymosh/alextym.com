import type { AssistantMessage, HandoffState, Message } from "../types/chat";

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
