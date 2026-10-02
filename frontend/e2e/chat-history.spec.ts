import { expect, test } from "@playwright/test";
import {
  CHAT_HISTORY_ITEM_MAX_CHARS,
  CHAT_HISTORY_LIMIT,
  CHAT_HISTORY_TOTAL_MAX_CHARS,
  ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS,
  ESCALATION_TRANSCRIPT_LIMIT,
  ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS,
} from "../content/chat";
import { buildChatHistory } from "../lib/chat-history";
import { buildEscalationTranscript } from "../lib/chat-transcript";
import type { Message, MessageRole } from "../types/chat";

// Pure history checks use the existing runner without a browser or API calls.
const builders = [
  {
    name: "AI history",
    build: buildChatHistory,
    itemLimit: CHAT_HISTORY_LIMIT,
    itemMaxChars: CHAT_HISTORY_ITEM_MAX_CHARS,
    totalMaxChars: CHAT_HISTORY_TOTAL_MAX_CHARS,
  },
  {
    name: "repeat handoff transcript",
    build: buildEscalationTranscript,
    itemLimit: ESCALATION_TRANSCRIPT_LIMIT,
    itemMaxChars: ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS,
    totalMaxChars: ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS,
  },
];

for (const { name, build, itemLimit, itemMaxChars, totalMaxChars } of builders) {
  test.describe(name, () => {
    test("preserves all speakers in order without changing visible messages", () => {
      const messages = [
        message("user", "Which project should I read about?"),
        message("assistant", "You can ask Alex directly."),
        message("alex", "I suggest my portfolio website."),
        message("user", "Which part should I start with?"),
        message("alex", "Start with the chat page."),
        message("assistant", "The live chat has ended."),
      ];
      const original = structuredClone(messages);

      expect(build(messages)).toEqual([
        { role: "user", content: "Which project should I read about?" },
        { role: "assistant", content: "You can ask Alex directly." },
        { role: "owner", content: "I suggest my portfolio website." },
        { role: "user", content: "Which part should I start with?" },
        { role: "owner", content: "Start with the chat page." },
        { role: "assistant", content: "The live chat has ended." },
      ]);
      expect(messages).toEqual(original);
    });

    test("preserves an ordinary AI conversation", () => {
      expect(build([
        message("user", "Tell me about Alex."),
        message("assistant", "Which part of his profile interests you?"),
      ])).toEqual([
        { role: "user", content: "Tell me about Alex." },
        { role: "assistant", content: "Which part of his profile interests you?" },
      ]);
    });

    test("omits blank messages and accepts an empty conversation", () => {
      expect(build([])).toEqual([]);
      expect(build([
        message("user", " \t "),
        message("alex", "\n "),
        message("alex", "  First\n\t second   third  "),
        message("assistant", ""),
      ])).toEqual([{ role: "owner", content: "First second third" }]);
    });

    test("compacts and clips owner text to the per-message limit", () => {
      expect(build([
        message("alex", ` \n${"x".repeat(itemMaxChars)} trailing text `),
      ])).toEqual([{ role: "owner", content: "x".repeat(itemMaxChars) }]);
    });

    test("counts owner replies toward the limit and retains the newest ones", () => {
      const messages = Array.from({ length: itemLimit + 3 }, (_, index) =>
        message("alex", `Owner reply ${index}`),
      );
      const result = build(messages);

      expect(result).toHaveLength(itemLimit);
      expect(result[0]).toEqual({ role: "owner", content: "Owner reply 3" });
      expect(result.at(-1)).toEqual({
        role: "owner", content: `Owner reply ${itemLimit + 2}`,
      });
      expect(result.every((item) => item.role === "owner")).toBe(true);
    });

    test("counts owner text toward the total character budget", () => {
      const newest = Array.from(
        { length: totalMaxChars / itemMaxChars },
        (_, index) => message("alex", String(index).repeat(itemMaxChars)),
      );
      const result = build([message("user", "Older message"), ...newest]);

      expect(result).toHaveLength(newest.length);
      expect(result.reduce((total, item) => total + item.content.length, 0))
        .toBe(totalMaxChars);
      expect(result[0]).toEqual({ role: "owner", content: "0".repeat(itemMaxChars) });
      expect(result.at(-1)?.content).toBe(newest.at(-1)?.text);
    });

    test("stops at the first overflowing message without skipping to older text", () => {
      const newest = Array.from(
        { length: totalMaxChars / itemMaxChars },
        (_, index) => message("alex", "n".repeat(itemMaxChars - (index === 0 ? 1 : 0))),
      );
      const result = build([
        message("user", "a"),
        message("alex", "Does not fit"),
        ...newest,
      ]);

      expect(result).toHaveLength(newest.length);
      expect(result.reduce((total, item) => total + item.content.length, 0))
        .toBe(totalMaxChars - 1);
      expect(result.every((item) => /^n+$/.test(item.content))).toBe(true);
    });
  });
}

function message(role: MessageRole, text: string): Message {
  if (role === "assistant") {
    return { id: text, role, text, handoffSuggested: false, handoffReason: null };
  }
  return { id: text, role, text };
}
