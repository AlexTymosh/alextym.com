import { chatNoticeCopy } from "../content/chat";
import type { AssistantMessage, ChatHistoryMessage } from "../types/chat";
import {
  fetchJsonChatResponse,
  isChatStreamError,
  streamChatResponse,
} from "./chat-api";
import { isAbortError } from "./chat-errors";
import type { StreamTextRenderer } from "./stream-text-renderer";

type AssistantPatch = Partial<Omit<AssistantMessage, "id" | "role">>;

type ChatResponseFlowOptions = {
  message: string;
  history: ChatHistoryMessage[];
  signal: AbortSignal;
  renderer: StreamTextRenderer;
  onAssistantPatch: (patch: AssistantPatch) => void;
  onNotice: (notice: string) => void;
};

// Allow deterministic testing of transport failures without a server or browser.
export type ChatResponseFlowTransport = {
  stream: typeof streamChatResponse;
  fetchJson: typeof fetchJsonChatResponse;
};

const DEFAULT_TRANSPORT: ChatResponseFlowTransport = {
  stream: streamChatResponse,
  fetchJson: fetchJsonChatResponse,
};

/** Run an assistant response, including the existing SSE/JSON fallback policy.
 * The controller still owns React state, request cancellation and focus.
 */
export async function runChatResponseFlow(
  {
    message,
    history,
    signal,
    renderer,
    onAssistantPatch,
    onNotice,
  }: ChatResponseFlowOptions,
  transport: ChatResponseFlowTransport = DEFAULT_TRANSPORT,
): Promise<void> {
  let rawStreamText = "";
  let pendingSources: AssistantMessage["sources"] | undefined;

  try {
    await transport.stream({
      message,
      history,
      signal,
      onToken: (token) => {
        rawStreamText += token;
        renderer.append(token);
      },
      onSources: (sources) => {
        pendingSources = sources;
      },
      onDone: (done) =>
        onAssistantPatch({
          confidence: done.confidence,
          notEnoughData: done.not_enough_data,
          retrievalStatus: done.retrieval_status,
          handoffSuggested: done.handoff_suggested,
          handoffReason: done.handoff_reason ?? null,
          languageUnsupported: done.language_unsupported,
          userRequestedHuman: done.user_requested_human,
        }),
    });
    await renderer.finish();
    if (pendingSources?.length) {
      onAssistantPatch({ sources: pendingSources });
    }
  } catch (error) {
    if (isAbortError(error)) {
      return;
    }

    if (isChatStreamError(error) && error.kind === "backend_error") {
      renderer.flush();
      if (rawStreamText) {
        onNotice(error.message || chatNoticeCopy.assistantUnavailable);
        return;
      }

      onAssistantPatch({
        text: error.message || chatNoticeCopy.assistantErrorMessage,
        confidence: "low",
        notEnoughData: false,
        handoffSuggested: false,
        handoffReason: null,
      });
      onNotice(chatNoticeCopy.assistantUnavailable);
      return;
    }

    if (!rawStreamText) {
      try {
        const fallbackResponse = await transport.fetchJson(message, history, signal);
        renderer.append(fallbackResponse.answer);
        await renderer.finish();
        onAssistantPatch({
          sources: fallbackResponse.sources,
          confidence: fallbackResponse.confidence,
          notEnoughData: fallbackResponse.not_enough_data,
          retrievalStatus: fallbackResponse.retrieval_status,
          handoffSuggested: fallbackResponse.handoff_suggested,
          handoffReason: fallbackResponse.handoff_reason ?? null,
          languageUnsupported: fallbackResponse.language_unsupported,
          userRequestedHuman: fallbackResponse.user_requested_human,
        });
        onNotice(chatNoticeCopy.streamingFallbackUsed);
      } catch (fallbackError) {
        if (!isAbortError(fallbackError)) {
          onAssistantPatch({
            text: chatNoticeCopy.assistantErrorMessage,
            confidence: "low",
            notEnoughData: false,
            handoffSuggested: false,
            handoffReason: null,
          });
          onNotice(chatNoticeCopy.assistantUnavailable);
        }
      }
    } else {
      renderer.flush();
      onNotice(chatNoticeCopy.streamingEndedEarly);
    }
  } finally {
    renderer.cancel();
  }
}
