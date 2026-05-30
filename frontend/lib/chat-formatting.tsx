import type { ReactNode } from "react";
import type { HandoffState, Message } from "../types/chat";

export function handoffStatusCopy(
  state: HandoffState,
  expiresInSeconds: number | null,
): string {
  const expirySuffix = expiresInSeconds
    ? ` This session stays open for about ${formatDuration(expiresInSeconds)}.`
    : "";

  if (state === "connected") {
    return (
      "Alex has replied in this chat. New messages you send here will go " +
      `to Alex.${expirySuffix}`
    );
  }
  if (state === "closed") {
    return (
      "This handoff session has closed. You can continue with the AI " +
      "assistant or request a new connection."
    );
  }
  if (state === "error") {
    return "The live handoff connection is reconnecting. Keep this page open.";
  }
  return (
    "Waiting for Alex. His replies will appear here automatically, and " +
    `new messages you send here will go to Alex.${expirySuffix}`
  );
}

export function formatDuration(totalSeconds: number): string {
  const minutes = Math.max(1, Math.round(totalSeconds / 60));
  if (minutes < 60) {
    return `${minutes} minutes`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours} ${hours === 1 ? "hour" : "hours"}`;
}

export function getRenderableMessageText(
  message: Message,
  thinkingLabel: string,
): string {
  if (message.text) {
    return message.role === "alex" ? `Alex:\n\n${message.text}` : message.text;
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
