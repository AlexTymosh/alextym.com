import { useEffect, useState } from "react";

export function useAnimatedLabel(
  active: boolean,
  messages: readonly string[],
  messageIntervalMs = 1800,
  dotIntervalMs = 500,
): string {
  const [messageIndex, setMessageIndex] = useState(0);
  const [dotCount, setDotCount] = useState(1);

  useEffect(() => {
    if (!active) {
      return;
    }

    const dotIntervalId = window.setInterval(() => {
      setDotCount((current) => (current >= 3 ? 1 : current + 1));
    }, dotIntervalMs);

    const messageIntervalId = window.setInterval(() => {
      setMessageIndex((current) => (current + 1) % messages.length);
    }, messageIntervalMs);

    return () => {
      window.clearInterval(dotIntervalId);
      window.clearInterval(messageIntervalId);
    };
  }, [active, dotIntervalMs, messageIntervalMs, messages]);

  const currentMessage = active
    ? messages[messageIndex % messages.length] || messages[0]
    : messages[0];
  const currentDotCount = active ? dotCount : 1;

  return `${currentMessage}${".".repeat(currentDotCount)}`;
}

