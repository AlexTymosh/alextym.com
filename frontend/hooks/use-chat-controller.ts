import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

import { chatHandoffCopy, chatNoticeCopy, chatShellCopy } from "../content/chat";
import { useEscalationStream } from "../hooks/use-escalation-stream";
import { fetchJsonChatResponse, streamChatResponse } from "../lib/chat-api";
import { isAbortError } from "../lib/chat-errors";
import { buildChatHistory } from "../lib/chat-history";
import {
  hasPendingHandoffSuggestion,
  isHandoffConfirmationText,
  isHandoffRequestText,
  isHumanHandoffActive,
  shouldAssistantSuggestHandoff,
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
  const [dismissedHandoffMessageCount, setDismissedHandoffMessageCount] =
    useState<number | null>(null);
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

  const shouldShowHandoffPrompt = useMemo(() => {
    if (
      isThinking ||
      isEscalating ||
      isSendingHandoffMessage ||
      isClosingHandoff ||
      escalationSent ||
      !messages.length
    ) {
      return false;
    }
    if (dismissedHandoffMessageCount === messages.length) {
      return false;
    }

    const latestAssistantMessage = [...messages]
      .reverse()
      .find((message) => message.role === "assistant" && message.text.trim());
    const latestUserMessage = [...messages]
      .reverse()
      .find((message) => message.role === "user" && message.text.trim());

    return Boolean(
      (latestAssistantMessage &&
        shouldAssistantSuggestHandoff(latestAssistantMessage)) ||
        (latestUserMessage && isHandoffRequestText(latestUserMessage.text)),
    );
  }, [
    dismissedHandoffMessageCount,
    escalationSent,
    isClosingHandoff,
    isEscalating,
    isSendingHandoffMessage,
    isThinking,
    messages,
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
    setDismissedHandoffMessageCount(null);
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
      { id: assistantId, role: "assistant", text: "" },
    ]);
    setInput("");
    setIsThinking(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);
    setDismissedHandoffMessageCount(null);

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

    if (
      hasPendingHandoffSuggestion(messages) &&
      isHandoffConfirmationText(trimmedInput)
    ) {
      appendLocalUserMessage(trimmedInput);
      return;
    }

    if (isHandoffRequestText(trimmedInput)) {
      appendLocalUserMessage(trimmedInput);
      return;
    }

    const assistantId = createMessageId("assistant");
    const history = buildChatHistory(messages);
    let rawStreamText = "";
    let pendingSources: Message["sources"] | undefined;

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
      { id: assistantId, role: "assistant", text: "" },
    ]);
    setInput("");
    setIsThinking(true);
    setNotice(null);
    setHandoffUnavailableMessage(null);
    setDismissedHandoffMessageCount(null);

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
              notEnoughData: true,
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

  function appendLocalUserMessage(messageText: string) {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setMessages((currentMessages) => [
      ...currentMessages,
      { id: createMessageId("user"), role: "user", text: messageText },
    ]);
    setInput("");
    setNotice(null);
    setHandoffUnavailableMessage(null);
    setDismissedHandoffMessageCount(null);
    focusMessageInputSoon();
  }

  function updateAssistantMessage(messageId: string, patch: Partial<Message>) {
    setMessages((currentMessages) =>
      currentMessages.map((message) =>
        message.id === messageId ? { ...message, ...patch } : message,
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
      setDismissedHandoffMessageCount(null);
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
      setDismissedHandoffMessageCount(messages.length);
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
        },
      ]);
    } catch (error) {
      if (isHandoffUnavailableError(error)) {
        showHandoffUnavailableMessage(error.message);
        setDismissedHandoffMessageCount(messages.length);
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
        },
      ]);
    } catch {
      setNotice(chatHandoffCopy.closeFailureMessage);
    } finally {
      setIsClosingHandoff(false);
      focusMessageInputSoon();
    }
  }

  function continueWithAi() {
    setDismissedHandoffMessageCount(messages.length);
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
    continueWithAi,
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
