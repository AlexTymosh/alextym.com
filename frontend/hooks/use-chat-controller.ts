import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

import { chatHandoffCopy, chatNoticeCopy, chatShellCopy } from "../content/chat";
import { useEscalationStream } from "../hooks/use-escalation-stream";
import {
  fetchJsonChatResponse,
  isChatStreamError,
  streamChatResponse,
} from "../lib/chat-api";
import { isAbortError } from "../lib/chat-errors";
import { buildChatHistory } from "../lib/chat-history";
import {
  getPendingHandoffSuggestion,
  isHumanHandoffActive,
} from "../lib/chat-handoff";
import { createMessageId } from "../lib/chat-message-id";
import {
  chooseScriptedResponse,
  waitForScriptedResponse,
} from "../lib/chat-scripted-responses";
import { buildEscalationTranscript } from "../lib/chat-transcript";
import {
  EscalationApiError,
  isHandoffUnavailableError,
  normaliseHandoffState,
  submitEscalation,
  submitEscalationClose,
  submitEscalationMessage,
} from "../lib/escalation-api";
import { createStreamTextRenderer } from "../lib/stream-text-renderer";
import type {
  AssistantMessage,
  EscalationStreamClosedReason,
  HandoffState,
  Message,
  QuickPrompt,
} from "../types/chat";

const DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE =
  chatHandoffCopy.defaultUnavailableMessage;

const HANDOFF_NAME_REQUEST_MESSAGE = chatHandoffCopy.nameRequestMessage;

type UseChatControllerOptions = {
  focusMessageInputSoon: () => void;
};

export function useChatController({
  focusMessageInputSoon,
}: UseChatControllerOptions) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [warmupStatus, setWarmupStatus] = useState<
    "warming" | "ready" | "error"
  >("warming");
  const [isThinking, setIsThinking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [handoffUnavailableMessage, setHandoffUnavailableMessage] = useState<
    string | null
  >(null);
  const [isEscalating, setIsEscalating] = useState(false);
  const [isSendingHandoffMessage, setIsSendingHandoffMessage] = useState(false);
  const [isClosingHandoff, setIsClosingHandoff] = useState(false);
  const [escalationSent, setEscalationSent] = useState(false);
  const [handoffId, setHandoffId] = useState<string | null>(null);
  const [handoffState, setHandoffState] = useState<HandoffState>("idle");
  const [dismissedHandoffMessageId, setDismissedHandoffMessageId] = useState<
    string | null
  >(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleEscalationStreamMeta = useCallback(() => {
    setNotice(null);
    setHandoffUnavailableMessage(null);
    setHandoffState((currentState) =>
      currentState === "connected" ? "connected" : "waiting_for_alex",
    );
  }, []);

  const handleEscalationStreamMessage = useCallback(
    (message: { id: string; content: string }) => {
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: message.id, role: "alex", text: message.content },
      ]);
      setHandoffState("connected");
      setNotice(null);
      setHandoffUnavailableMessage(null);
    },
    [],
  );

  const handleEscalationStreamClosed = useCallback(
    (reason: EscalationStreamClosedReason) => {
      setHandoffState("closed");
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          text: getHandoffClosedMessage(reason),
          handoffSuggested: false,
          handoffReason: null,
        },
      ]);
    },
    [],
  );

  const handleEscalationStreamError = useCallback(() => {
    setHandoffState((currentState) =>
      currentState === "connected" ? "connected" : "error",
    );
    setNotice(chatHandoffCopy.reconnectingNotice);
  }, []);

  const {
    closeEscalationStream,
    openEscalationStream,
    resetEscalationStream,
  } = useEscalationStream({
    onClosed: handleEscalationStreamClosed,
    onError: handleEscalationStreamError,
    onMessage: handleEscalationStreamMessage,
    onMeta: handleEscalationStreamMeta,
  });

  useEffect(() => {
    let isMounted = true;

    fetch("/api/warmup", { method: "GET" })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Warm-up failed");
        }
        if (isMounted) {
          setWarmupStatus("ready");
        }
      })
      .catch(() => {
        if (isMounted) {
          setWarmupStatus("error");
        }
      });

    return () => {
      isMounted = false;
      abortControllerRef.current?.abort();
      closeEscalationStream();
    };
  }, [closeEscalationStream]);

  useEffect(() => {
    if (isThinking || isEscalating || isSendingHandoffMessage || isClosingHandoff) {
      return;
    }
    focusMessageInputSoon();
  }, [
    focusMessageInputSoon,
    handoffState,
    isClosingHandoff,
    isEscalating,
    isSendingHandoffMessage,
    isThinking,
  ]);

  const inputPlaceholder = useMemo(() => {
    if (isHumanHandoffActive(handoffId, handoffState)) {
      return chatShellCopy.handoffInputPlaceholder;
    }
    if (handoffState === "closed") {
      return chatShellCopy.closedInputPlaceholder;
    }
    return chatShellCopy.defaultInputPlaceholder;
  }, [handoffId, handoffState]);

  const pendingHandoffSuggestion = useMemo(
    () => getPendingHandoffSuggestion(messages),
    [messages],
  );

  const shouldShowHandoffPrompt = useMemo(() => {
    if (
      isThinking ||
      isEscalating ||
      isSendingHandoffMessage ||
      isClosingHandoff ||
      escalationSent
    ) {
      return false;
    }
    if (
      !pendingHandoffSuggestion ||
      dismissedHandoffMessageId === pendingHandoffSuggestion.id
    ) {
      return false;
    }

    return true;
  }, [
    dismissedHandoffMessageId,
    escalationSent,
    isClosingHandoff,
    isEscalating,
    isSendingHandoffMessage,
    isThinking,
    pendingHandoffSuggestion,
  ]);

  const isInputDisabled =
    isThinking || isEscalating || isSendingHandoffMessage || isClosingHandoff;
  const isSubmitDisabled = isInputDisabled || !input.trim();
  const hasActiveHandoff = isHumanHandoffActive(handoffId, handoffState);

  function resetChat() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    resetEscalationStream();
    setInput("");
    setMessages([]);
    setIsThinking(false);
    setNotice(null);
    setHandoffUnavailableMessage(null);
    setIsEscalating(false);
    setIsSendingHandoffMessage(false);
    setIsClosingHandoff(false);
    setEscalationSent(false);
    setHandoffId(null);
    setHandoffState("idle");
    setDismissedHandoffMessageId(null);
    focusMessageInputSoon();
  }

  async function sendScriptedResponse(prompt: QuickPrompt) {
    if (isInputDisabled) {
      return;
    }

    const assistantId = createMessageId("assistant");
    const abortController = new AbortController();

    abortControllerRef.current?.abort();
    abortControllerRef.current = abortController;

    setMessages((currentMessages) => [
      ...currentMessages,
      { id: createMessageId("user"), role: "user", text: prompt.label },
      {
        id: assistantId,
        role: "assistant",
        text: "",
        handoffSuggested: prompt.handoffSuggested,
        handoffReason: prompt.handoffReason,
      },
    ]);
    setInput("");
    setIsThinking(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);

    try {
      await waitForScriptedResponse(abortController.signal);
      updateAssistantMessage(assistantId, {
        text: chooseScriptedResponse(prompt.responses),
      });
    } catch (error) {
      if (!isAbortError(error)) {
        updateAssistantMessage(assistantId, {
          text: chatNoticeCopy.assistantErrorMessage,
          confidence: "low",
          notEnoughData: true,
          handoffSuggested: false,
          handoffReason: null,
        });
        setNotice(chatNoticeCopy.assistantUnavailable);
      }
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
      setIsThinking(false);
      focusMessageInputSoon();
    }
  }

  async function sendMessage(messageText: string) {
    const trimmedInput = messageText.trim();
    if (!trimmedInput) {
      return;
    }
    if (isInputDisabled) {
      return;
    }

    if (isHumanHandoffActive(handoffId, handoffState)) {
      await sendMessageToAlex(trimmedInput);
      return;
    }

    const assistantId = createMessageId("assistant");
    const history = buildChatHistory(messages);
    let rawStreamText = "";
    let pendingSources: AssistantMessage["sources"] | undefined;

    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const renderer = createStreamTextRenderer({
      signal: abortController.signal,
      onUpdate: (text) => updateAssistantMessage(assistantId, { text }),
    });

    setMessages((currentMessages) => [
      ...currentMessages,
      { id: createMessageId("user"), role: "user", text: trimmedInput },
      {
        id: assistantId,
        role: "assistant",
        text: "",
        handoffSuggested: false,
        handoffReason: null,
      },
    ]);
    setInput("");
    setIsThinking(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);

    try {
      await streamChatResponse({
        message: trimmedInput,
        history,
        signal: abortController.signal,
        onToken: (token) => {
          rawStreamText += token;
          renderer.append(token);
        },
        onSources: (sources) => {
          pendingSources = sources;
        },
        onDone: (done) =>
          updateAssistantMessage(assistantId, {
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
        updateAssistantMessage(assistantId, { sources: pendingSources });
      }
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }

      if (isChatStreamError(error) && error.kind === "backend_error") {
        renderer.flush();
        if (rawStreamText) {
          setNotice(error.message || chatNoticeCopy.assistantUnavailable);
          return;
        }

        updateAssistantMessage(assistantId, {
          text: error.message || chatNoticeCopy.assistantErrorMessage,
          confidence: "low",
          notEnoughData: false,
          handoffSuggested: false,
          handoffReason: null,
        });
        setNotice(chatNoticeCopy.assistantUnavailable);
        return;
      }

      if (!rawStreamText) {
        try {
          const fallbackResponse = await fetchJsonChatResponse(
            trimmedInput,
            history,
            abortController.signal,
          );
          renderer.append(fallbackResponse.answer);
          await renderer.finish();
          updateAssistantMessage(assistantId, {
            sources: fallbackResponse.sources,
            confidence: fallbackResponse.confidence,
            notEnoughData: fallbackResponse.not_enough_data,
            retrievalStatus: fallbackResponse.retrieval_status,
            handoffSuggested: fallbackResponse.handoff_suggested,
            handoffReason: fallbackResponse.handoff_reason ?? null,
            languageUnsupported: fallbackResponse.language_unsupported,
            userRequestedHuman: fallbackResponse.user_requested_human,
          });
          setNotice(chatNoticeCopy.streamingFallbackUsed);
        } catch (fallbackError) {
          if (!isAbortError(fallbackError)) {
            updateAssistantMessage(assistantId, {
              text: chatNoticeCopy.assistantErrorMessage,
              confidence: "low",
              notEnoughData: false,
              handoffSuggested: false,
              handoffReason: null,
            });
            setNotice(chatNoticeCopy.assistantUnavailable);
          }
        }
      } else {
        renderer.flush();
        setNotice(chatNoticeCopy.streamingEndedEarly);
      }
    } finally {
      renderer.cancel();
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
      setIsThinking(false);
      focusMessageInputSoon();
    }
  }

  function updateAssistantMessage(
    messageId: string,
    patch: Partial<Omit<AssistantMessage, "id" | "role">>,
  ) {
    setMessages((currentMessages) =>
      currentMessages.map((message) =>
        message.id === messageId && message.role === "assistant"
          ? { ...message, ...patch }
          : message,
      ),
    );
  }

  async function sendMessageToAlex(messageText: string) {
    if (!handoffId || !isHumanHandoffActive(handoffId, handoffState)) {
      return;
    }

    setIsSendingHandoffMessage(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);

    try {
      await submitEscalationMessage(handoffId, messageText);
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: createMessageId("user"), role: "user", text: messageText },
      ]);
      setInput("");
    } catch (error) {
      if (isHandoffUnavailableError(error)) {
        showHandoffUnavailableMessage(error.message);
        return;
      }
      if (error instanceof EscalationApiError && error.status === 429) {
        setNotice(chatHandoffCopy.messageDailyLimitMessage);
        return;
      }
      setNotice(chatHandoffCopy.sendFailureMessage);
    } finally {
      setIsSendingHandoffMessage(false);
      focusMessageInputSoon();
    }
  }

  async function connectWithAlex() {
    if (isEscalating || isThinking || !messages.length) {
      return;
    }

    setIsEscalating(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);

    try {
      const response = await submitEscalation(
        buildEscalationTranscript(messages),
      );
      const nextHandoffId = response.handoff_id || null;
      const nextState = normaliseHandoffState(response.state);

      setEscalationSent(true);
      setDismissedHandoffMessageId(pendingHandoffSuggestion?.id ?? null);
      setHandoffId(nextHandoffId);
      setHandoffState(nextHandoffId ? nextState : "idle");

      if (nextHandoffId) {
        openEscalationStream(nextHandoffId);
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          text: nextHandoffId
            ? HANDOFF_NAME_REQUEST_MESSAGE
            : chatHandoffCopy.notificationSentMessage,
          handoffSuggested: false,
          handoffReason: null,
        },
      ]);
    } catch (error) {
      if (isHandoffUnavailableError(error)) {
        showHandoffUnavailableMessage(error.message);
        setDismissedHandoffMessageId(pendingHandoffSuggestion?.id ?? null);
        return;
      }
      if (error instanceof EscalationApiError && error.status === 429) {
        setNotice(chatHandoffCopy.connectionDailyLimitMessage);
        return;
      }
      setNotice(chatHandoffCopy.connectFailureMessage);
    } finally {
      setIsEscalating(false);
      focusMessageInputSoon();
    }
  }

  async function closeHandoff() {
    if (!handoffId || handoffState === "closed" || isClosingHandoff) {
      return;
    }

    setIsClosingHandoff(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);

    try {
      await submitEscalationClose(handoffId);
      closeEscalationStream();
      setHandoffState("closed");
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          text: getHandoffClosedMessage("session_closed"),
          handoffSuggested: false,
          handoffReason: null,
        },
      ]);
    } catch {
      setNotice(chatHandoffCopy.closeFailureMessage);
    } finally {
      setIsClosingHandoff(false);
      focusMessageInputSoon();
    }
  }

  function dismissHandoffSuggestion() {
    if (pendingHandoffSuggestion) {
      setDismissedHandoffMessageId(pendingHandoffSuggestion.id);
    }
    setNotice(null);
    setHandoffUnavailableMessage(null);
    focusMessageInputSoon();
  }

  function showHandoffUnavailableMessage(message: string) {
    setHandoffUnavailableMessage(message || DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE);
    setNotice(null);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }

    event.preventDefault();
    void sendMessage(input);
  }

  return {
    closeHandoff,
    connectWithAlex,
    dismissHandoffSuggestion,
    handleInputKeyDown,
    handleSubmit,
    handoffId,
    handoffState,
    handoffUnavailableMessage,
    hasActiveHandoff,
    input,
    inputPlaceholder,
    isClosingHandoff,
    isEscalating,
    isInputDisabled,
    isSendingHandoffMessage,
    isSubmitDisabled,
    isThinking,
    messages,
    notice,
    resetChat,
    sendScriptedResponse,
    setInput,
    shouldShowHandoffPrompt,
    warmupStatus,
  };
}

function getHandoffClosedMessage(
  reason: EscalationStreamClosedReason,
): string {
  if (reason === "session_closed") {
    return chatHandoffCopy.closedByUserMessage;
  }

  if (reason === "session_expired") {
    return chatHandoffCopy.sessionExpiredMessage;
  }

  return chatHandoffCopy.sessionClosedMessage;
}
