import {
  CHAT_HISTORY_ITEM_MAX_CHARS,
  CHAT_HISTORY_LIMIT,
  CHAT_HISTORY_TOTAL_MAX_CHARS,
} from "../content/chat";
import type { ChatHistoryMessage, Message } from "../types/chat";

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
