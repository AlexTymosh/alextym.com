import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

import { chatHandoffCopy, chatNoticeCopy, chatShellCopy } from "../content/chat";
import { useEscalationStream } from "../hooks/use-escalation-stream";
import { runChatResponseFlow } from "../lib/chat-response-flow";
import { purgeDetachedHandoff } from "../lib/handoff-cleanup";
import { createChatRequestLifecycle } from "../lib/chat-request-lifecycle";
import { isAbortError } from "../lib/chat-errors";
import { buildChatHistory } from "../lib/chat-history";
import {
  getHandoffContactPath,
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
  const [handoffUnavailable, setHandoffUnavailable] = useState<
    { message: string; contactPath: string } | null
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
  const [requestLifecycle] = useState(createChatRequestLifecycle);

  const handleEscalationStreamMeta = useCallback(() => {
    setNotice(null);
    setHandoffUnavailable(null);
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
      setHandoffUnavailable(null);
    },
    [],
  );

  const handleEscalationStreamClosed = useCallback(
    (reason: EscalationStreamClosedReason) => {
      setHandoffState("closed");
      setEscalationSent(false);
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
      requestLifecycle.invalidate();
      closeEscalationStream();
    };
  }, [closeEscalationStream, requestLifecycle]);

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
    const detachedHandoffId = handoffId;
    requestLifecycle.invalidate();
    resetEscalationStream();
    if (detachedHandoffId) {
      void purgeDetachedHandoff(detachedHandoffId);
    }
    setInput("");
    setMessages([]);
    setIsThinking(false);
    setNotice(null);
    setHandoffUnavailable(null);
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
    if (isInputDisabled || requestLifecycle.hasActiveAssistant()) {
      return;
    }

    const assistantId = createMessageId("assistant");
    const request = requestLifecycle.beginAssistantRequest();

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
    setHandoffUnavailable(null);

    try {
      await waitForScriptedResponse(request.signal);
      if (request.isCurrent()) {
        updateAssistantMessage(assistantId, {
          text: chooseScriptedResponse(prompt.responses),
        });
      }
    } catch (error) {
      if (!isAbortError(error) && request.isCurrent()) {
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
      if (request.isCurrent()) {
        request.finish();
        setIsThinking(false);
        focusMessageInputSoon();
      }
    }
  }

  async function sendMessage(messageText: string) {
    const trimmedInput = messageText.trim();
    if (!trimmedInput) {
      return;
    }
    if (isInputDisabled || requestLifecycle.hasActiveAssistant()) {
      return;
    }

    if (isHumanHandoffActive(handoffId, handoffState)) {
      await sendMessageToAlex(trimmedInput);
      return;
    }

    const assistantId = createMessageId("assistant");
    const history = buildChatHistory(messages);

    const request = requestLifecycle.beginAssistantRequest();

    const renderer = createStreamTextRenderer({
      signal: request.signal,
      onUpdate: (text) => {
        if (request.isCurrent()) {
          updateAssistantMessage(assistantId, { text });
        }
      },
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
    setHandoffUnavailable(null);

    try {
      await runChatResponseFlow({
        message: trimmedInput,
        history,
        signal: request.signal,
        renderer,
        onAssistantPatch: (patch) => {
          if (request.isCurrent()) {
            updateAssistantMessage(assistantId, patch);
          }
        },
        onNotice: (nextNotice) => {
          if (request.isCurrent()) {
            setNotice(nextNotice);
          }
        },
      });
    } finally {
      if (request.isCurrent()) {
        request.finish();
        setIsThinking(false);
        focusMessageInputSoon();
      }
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

    const isCurrentSession = requestLifecycle.captureSession();
    setIsSendingHandoffMessage(true);
    setNotice(null);
    setHandoffUnavailable(null);

    try {
      await submitEscalationMessage(handoffId, messageText);
      if (!isCurrentSession()) {
        return;
      }
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: createMessageId("user"), role: "user", text: messageText },
      ]);
      setInput("");
    } catch (error) {
      if (!isCurrentSession()) {
        return;
      }
      if (isHandoffUnavailableError(error)) {
        showHandoffUnavailable(error);
        return;
      }
      if (error instanceof EscalationApiError && error.status === 429) {
        setNotice(chatHandoffCopy.messageDailyLimitMessage);
        return;
      }
      setNotice(chatHandoffCopy.sendFailureMessage);
    } finally {
      if (isCurrentSession()) {
        setIsSendingHandoffMessage(false);
        focusMessageInputSoon();
      }
    }
  }

  async function connectWithAlex() {
    if (isEscalating || isThinking || !messages.length) {
      return;
    }

    const isCurrentSession = requestLifecycle.captureSession();
    setIsEscalating(true);
    setNotice(null);
    setHandoffUnavailable(null);

    try {
      const response = await submitEscalation(
        buildEscalationTranscript(messages),
      );
      if (!isCurrentSession()) {
        // The server may have created a session after the local reset.
        void purgeDetachedHandoff(response.handoff_id);
        return;
      }
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
      if (!isCurrentSession()) {
        return;
      }
      if (isHandoffUnavailableError(error)) {
        showHandoffUnavailable(error);
        setDismissedHandoffMessageId(pendingHandoffSuggestion?.id ?? null);
        return;
      }
      if (error instanceof EscalationApiError && error.status === 429) {
        setNotice(chatHandoffCopy.connectionDailyLimitMessage);
        return;
      }
      setNotice(chatHandoffCopy.connectFailureMessage);
    } finally {
      if (isCurrentSession()) {
        setIsEscalating(false);
        focusMessageInputSoon();
      }
    }
  }

  async function closeHandoff() {
    if (!handoffId || handoffState === "closed" || isClosingHandoff) {
      return;
    }

    const isCurrentSession = requestLifecycle.captureSession();
    setIsClosingHandoff(true);
    setNotice(null);
    setHandoffUnavailable(null);

    try {
      await submitEscalationClose(handoffId);
      if (!isCurrentSession()) {
        return;
      }
      closeEscalationStream();
      setHandoffState("closed");
      setEscalationSent(false);
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
      if (isCurrentSession()) {
        setNotice(chatHandoffCopy.closeFailureMessage);
      }
    } finally {
      if (isCurrentSession()) {
        setIsClosingHandoff(false);
        focusMessageInputSoon();
      }
    }
  }

  function dismissHandoffSuggestion() {
    if (pendingHandoffSuggestion) {
      setDismissedHandoffMessageId(pendingHandoffSuggestion.id);
    }
    setNotice(null);
    setHandoffUnavailable(null);
    focusMessageInputSoon();
  }

  function showHandoffUnavailable(error: EscalationApiError) {
    setHandoffUnavailable({
      message: error.message || DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE,
      contactPath: getHandoffContactPath(error.contactPath),
    });
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
    handoffUnavailable,
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
