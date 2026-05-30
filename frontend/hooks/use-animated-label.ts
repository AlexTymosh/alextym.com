import { useEffect, useState } from "react";

type AnimationFrame = {
  active: boolean;
  tick: number;
};

const initialFrame: AnimationFrame = {
  active: false,
  tick: 0,
};

export function useAnimatedLabel(
  active: boolean,
  messages: readonly string[],
  messageIntervalMs = 3000,
  dotIntervalMs = 500,
): string {
  const [frame, setFrame] = useState<AnimationFrame>(initialFrame);

  useEffect(() => {
    if (!active) {
      const resetId = window.setTimeout(() => {
        setFrame(initialFrame);
      }, 0);

      return () => {
        window.clearTimeout(resetId);
      };
    }

    let tick = 0;
    const resetId = window.setTimeout(() => {
      setFrame({ active: true, tick: 0 });
    }, 0);

    const intervalId = window.setInterval(() => {
      tick += 1;
      setFrame({ active: true, tick });
    }, dotIntervalMs);

    return () => {
      window.clearTimeout(resetId);
      window.clearInterval(intervalId);
    };
  }, [active, dotIntervalMs]);

  const fallbackMessage = messages[0] || "";

  if (!active || !messages.length) {
    return `${fallbackMessage}.`;
  }

  const ticksPerMessage = Math.max(
    1,
    Math.round(messageIntervalMs / dotIntervalMs),
  );
  const lastMessageIndex = Math.max(0, messages.length - 1);
  const tick = frame.active ? frame.tick : 0;
  const messageIndex = Math.min(
    Math.floor(tick / ticksPerMessage),
    lastMessageIndex,
  );
  const dotCount = (tick % 3) + 1;

  return `${messages[messageIndex] || fallbackMessage}${".".repeat(dotCount)}`;
}
