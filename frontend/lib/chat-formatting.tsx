import type { ReactNode } from "react";
import type { HandoffState, Message } from "../types/chat";

export function handoffStatusCopy(state: HandoffState): string | null {
  if (state === "waiting_for_alex" || state === "connected") {
    return null;
  }
  if (state === "closed") {
    return (
      "This handoff session has closed. New messages go back to " +
      "the AI assistant."
    );
  }
  if (state === "error") {
    return "The live handoff connection is reconnecting. Keep this page open.";
  }
  return null;
}

export function getRenderableMessageText(
  message: Message,
  thinkingLabel: string,
): string {
  if (message.text) {
    return message.text;
  }

  return message.role === "assistant" ? thinkingLabel : "";
}

export function renderMessageText(text: string) {
  const normalizedText = text
    .replace(/:\s+[-*]\s+/g, ":\n- ")
    .replace(/\s+[-*]\s+(?=[A-ZА-ЯЁ0-9])/g, "\n- ");
  const lines = normalizedText.split(/\r?\n/);
  const nodes: ReactNode[] = [];
  let listItems: string[] = [];

  function flushList(key: string) {
    if (!listItems.length) {
      return;
    }

    nodes.push(
      <ul key={`list-${key}`}>
        {listItems.map((item, index) => (
          <li key={`${key}-${index}`}>{item}</li>
        ))}
      </ul>,
    );
    listItems = [];
  }

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();
    const bulletMatch = trimmedLine.match(/^[-*]\s+(.+)$/);

    if (bulletMatch) {
      listItems.push(bulletMatch[1]);
      return;
    }

    flushList(String(index));

    if (!trimmedLine) {
      nodes.push(
        <span
          key={`break-${index}`}
          className="message__break"
          aria-hidden="true"
        />,
      );
      return;
    }

    nodes.push(<p key={`paragraph-${index}`}>{trimmedLine}</p>);
  });

  flushList("end");

  return nodes.length ? nodes : <p>{normalizedText}</p>;
}

