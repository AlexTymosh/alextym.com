import {
  ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS,
  ESCALATION_TRANSCRIPT_LIMIT,
  ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS,
} from "../content/chat";
import type { EscalationTranscriptMessage, Message } from "../types/chat";

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
