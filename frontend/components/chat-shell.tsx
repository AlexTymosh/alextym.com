"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  ESCALATION_CONSENT_COPY,
  chatHandoffCopy,
  chatNoticeCopy,
  chatShellCopy,
  quickPrompts,
  thinkingMessages,
  warmupMessages,
} from "../content/chat";
import { useAnimatedLabel } from "../hooks/use-animated-label";
import { fetchJsonChatResponse, streamChatResponse } from "../lib/chat-api";
import {
  EscalationApiError,
  buildEscalationStreamUrl,
  closeEscalationStream,
  isHandoffUnavailableError,
  normaliseHandoffState,
  parseEscalationStreamClosedReason,
  parseEscalationStreamMessage,
  submitEscalation,
  submitEscalationClose,
  submitEscalationMessage,
} from "../lib/escalation-api";
import {
  buildChatHistory,
  buildEscalationTranscript,
  chooseScriptedResponse,
  createMessageId,
  hasPendingHandoffSuggestion,
  isAbortError,
  isHandoffConfirmationText,
  isHandoffRequestText,
  isHumanHandoffActive,
  shouldAssistantSuggestHandoff,
  waitForScriptedResponse,
} from "../lib/chat-state";
import {
  getRenderableMessageText,
  handoffStatusCopy,
  renderMessageText,
} from "../lib/chat-formatting";
import type {
  EscalationStreamClosedReason,
  HandoffState,
  Message,
  QuickPrompt,
} from "../types/chat";

const DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE =
  chatHandoffCopy.defaultUnavailableMessage;

const HANDOFF_NAME_REQUEST_MESSAGE = chatHandoffCopy.nameRequestMessage;

const STREAM_RENDER_TICK_MS = 100;
const STREAM_RENDER_BASE_CHARS = 6;
const STREAM_RENDER_MEDIUM_CHARS = 14;
const STREAM_RENDER_FAST_CHARS = 220;
const STREAM_RENDER_LARGE_BACKLOG = 720;
const STREAM_RENDER_MEDIUM_BACKLOG = 280;
const SOURCE_REVEAL_STEP_MS = 180;

type StreamTextRenderer = {
  append: (text: string) => void;
  cancel: () => void;
  finish: () => Promise<void>;
  flush: () => void;
};

type StreamTextRendererOptions = {
  signal: AbortSignal;
  onUpdate: (text: string) => void;
};

export function ChatShell() {
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
  const chatBodyRef = useRef<HTMLDivElement | null>(null);
  const messageInputRef = useRef<HTMLTextAreaElement | null>(null);
  const escalationEventSourceRef = useRef<EventSource | null>(null);
  const seenEscalationMessageIdsRef = useRef<Set<string>>(new Set());

  const warmupLabel = useAnimatedLabel(
    warmupStatus === "warming",
    warmupMessages,
  );
  const thinkingLabel = useAnimatedLabel(isThinking, thinkingMessages);

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
      closeEscalationStream(escalationEventSourceRef);
    };
  }, []);

  const statusLabel = useMemo(() => {
    if (handoffState === "connected") {
      return chatShellCopy.handoffConnectedStatus;
    }
    if (handoffState === "waiting_for_alex") {
      return chatShellCopy.handoffWaitingStatus;
    }
    if (handoffState === "error") {
      return chatShellCopy.handoffReconnectingStatus;
    }
    if (handoffState === "closed") {
      return chatShellCopy.handoffClosedStatus;
    }
    if (warmupStatus === "ready") {
      return chatShellCopy.readyStatus;
    }
    if (warmupStatus === "error") {
      return chatShellCopy.warmupUnavailableStatus;
    }
    return warmupLabel;
  }, [handoffState, warmupLabel, warmupStatus]);

  const inputPlaceholder = useMemo(() => {
    if (isHumanHandoffActive(handoffId, handoffState)) {
      return chatShellCopy.handoffInputPlaceholder;
    }
    if (handoffState === "closed") {
      return chatShellCopy.closedInputPlaceholder;
    }
    return chatShellCopy.defaultInputPlaceholder;
  }, [handoffId, handoffState]);

  const handoffStatusText = useMemo(() => {
    return handoffId ? handoffStatusCopy(handoffState) : null;
  }, [handoffId, handoffState]);

  const unavailableMessageCopy = useMemo(() => {
    if (!handoffUnavailableMessage) {
      return null;
    }
    return formatHandoffUnavailableMessage(handoffUnavailableMessage);
  }, [handoffUnavailableMessage]);

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

  useEffect(() => {
    const scrollToBottom = () => {
      const chatBody = chatBodyRef.current;
      if (!chatBody) {
        return;
      }
      chatBody.scrollTop = chatBody.scrollHeight;
    };

    const frameId = window.requestAnimationFrame(scrollToBottom);
    const fallbackId = window.setTimeout(scrollToBottom, 80);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(fallbackId);
    };
  }, [
    handoffState,
    handoffUnavailableMessage,
    messages,
    notice,
    shouldShowHandoffPrompt,
  ]);

  useEffect(() => {
    const chatBody = chatBodyRef.current;
    if (!chatBody) {
      return;
    }

    let frameId: number | null = null;
    const scrollToBottomSoon = () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = window.requestAnimationFrame(() => {
        chatBody.scrollTop = chatBody.scrollHeight;
        frameId = null;
      });
    };

    const observer = new MutationObserver(scrollToBottomSoon);
    observer.observe(chatBody, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, []);

  useEffect(() => {
    const textarea = messageInputRef.current;
    if (!textarea) {
      return;
    }

    const maxHeight = 132;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [input]);

  useEffect(() => {
    if (isThinking || isEscalating || isSendingHandoffMessage || isClosingHandoff) {
      return;
    }
    focusMessageInputSoon();
  }, [
    handoffState,
    isClosingHandoff,
    isEscalating,
    isSendingHandoffMessage,
    isThinking,
  ]);

  function focusMessageInputSoon() {
    window.setTimeout(() => {
      messageInputRef.current?.focus();
    }, 0);
  }

  function resetChat() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    closeEscalationStream(escalationEventSourceRef);
    seenEscalationMessageIdsRef.current.clear();
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
    if (isThinking || isEscalating || isSendingHandoffMessage || isClosingHandoff) {
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
    if (isThinking || isEscalating || isSendingHandoffMessage || isClosingHandoff) {
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
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: createMessageId("user"), role: "user", text: trimmedInput },
      ]);
      setInput("");
      setNotice(null);
      setHandoffUnavailableMessage(null);
      setDismissedHandoffMessageCount(null);
      focusMessageInputSoon();
      return;
    }

    if (isHandoffRequestText(trimmedInput)) {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: createMessageId("user"), role: "user", text: trimmedInput },
      ]);
      setInput("");
      setNotice(null);
      setHandoffUnavailableMessage(null);
      setDismissedHandoffMessageCount(null);
      focusMessageInputSoon();
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
        seenEscalationMessageIdsRef.current.clear();
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
      closeEscalationStream(escalationEventSourceRef);
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

  function openEscalationStream(nextHandoffId: string) {
    closeEscalationStream(escalationEventSourceRef);

    const eventSource = new EventSource(buildEscalationStreamUrl(nextHandoffId));
    escalationEventSourceRef.current = eventSource;

    eventSource.addEventListener("meta", () => {
      setNotice(null);
      setHandoffUnavailableMessage(null);
      setHandoffState((currentState) =>
        currentState === "connected" ? "connected" : "waiting_for_alex",
      );
    });

    eventSource.addEventListener("message", (event) => {
      const message = parseEscalationStreamMessage(event);
      if (!message) {
        return;
      }

      if (seenEscalationMessageIdsRef.current.has(message.id)) {
        return;
      }
      seenEscalationMessageIdsRef.current.add(message.id);

      setMessages((currentMessages) => [
        ...currentMessages,
        { id: message.id, role: "alex", text: message.content },
      ]);
      setHandoffState("connected");
      setNotice(null);
      setHandoffUnavailableMessage(null);
    });

    eventSource.addEventListener("closed", (event) => {
      const reason = parseEscalationStreamClosedReason(event);
      closeEscalationStream(escalationEventSourceRef);
      setHandoffState("closed");
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          text: getHandoffClosedMessage(reason),
        },
      ]);
    });

    eventSource.addEventListener("error", () => {
      setHandoffState((currentState) =>
        currentState === "connected" ? "connected" : "error",
      );
      setNotice(chatHandoffCopy.reconnectingNotice);
    });
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

  return (
    <section className="chat-shell" aria-label={chatShellCopy.ariaLabel}>
      <div className="chat-shell__header">
        <div className="chat-shell__title">
          <span
            className={`status-dot status-dot--${warmupStatus}`}
            aria-hidden="true"
          />
          <div>
            <h1>{chatShellCopy.title}</h1>
            <p>{statusLabel}</p>
          </div>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={resetChat}
          aria-label={chatShellCopy.resetLabel}
        >
          <span aria-hidden="true">R</span>
        </button>
      </div>

      <div
        ref={chatBodyRef}
        className={
          messages.length === 0
            ? "chat-shell__body chat-shell__body--empty"
            : "chat-shell__body"
        }
      >
        {messages.length === 0 ? (
          <div className="chat-shell__empty">
            <div className="assistant-orb" aria-hidden="true">
              {"{ }"}
            </div>
            <h2>{chatShellCopy.introTitle}</h2>
            <p>{chatShellCopy.introDescription}</p>
            <div className="prompt-list" aria-label={chatShellCopy.quickPromptsAriaLabel}>
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt.label}
                  type="button"
                  className="prompt-button"
                  onClick={() => void sendScriptedResponse(prompt)}
                  disabled={
                    isThinking ||
                    isEscalating ||
                    isSendingHandoffMessage ||
                    isClosingHandoff
                  }
                >
                  <span className="prompt-button__icon" aria-hidden="true">
                    {">"}
                  </span>
                  <span>{prompt.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="message-list" aria-live="polite">
            {messages.map((message, index) => (
              <div
                key={message.id || `${message.role}-${index}`}
                className={`message message--${message.role}`}
              >
                {message.role === "alex" ? (
                  <div className="message__sender">
                    {chatShellCopy.messageSenderOwner}
                  </div>
                ) : null}
                <div className="message__content">
                  {renderMessageText(
                    getRenderableMessageText(message, thinkingLabel),
                  )}
                </div>
                {message.role === "assistant" ? (
                  <DelayedMessageSources
                    key={`${message.id}-${message.sources?.length ?? 0}`}
                    message={message}
                  />
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>

      {shouldShowHandoffPrompt ? (
        <div
          className="message message--assistant handoff-prompt"
          role="region"
          aria-label={chatShellCopy.handoffPromptAriaLabel}
        >
          <div className="message__content">
            <p>
              <strong>{chatShellCopy.handoffPromptTitle}</strong>
            </p>
            <p>{ESCALATION_CONSENT_COPY}</p>
          </div>
          <div className="prompt-list" aria-label={chatShellCopy.handoffActionsAriaLabel}>
            <button
              type="button"
              className="prompt-button"
              onClick={() => void connectWithAlex()}
              disabled={isEscalating || isClosingHandoff}
            >
              <span className="prompt-button__icon" aria-hidden="true">
                {">"}
              </span>
              <span>
                {isEscalating
                  ? chatShellCopy.handoffConnectingLabel
                  : chatShellCopy.handoffConnectLabel}
              </span>
            </button>
            <button
              type="button"
              className="prompt-button"
              onClick={continueWithAi}
              disabled={isClosingHandoff}
            >
              <span className="prompt-button__icon" aria-hidden="true">
                {">"}
              </span>
              <span>{chatShellCopy.handoffContinueLabel}</span>
            </button>
          </div>
        </div>
      ) : null}

      {isHumanHandoffActive(handoffId, handoffState) ? (
        <button
          type="button"
          className="handoff-toolbar"
          onClick={() => void closeHandoff()}
          disabled={isClosingHandoff}
        >
          {isClosingHandoff
            ? chatShellCopy.handoffClosingLabel
            : chatShellCopy.handoffCloseLabel}
        </button>
      ) : null}

      {handoffStatusText ? (
        <p className="chat-shell__notice chat-shell__notice--handoff">
          {handoffStatusText}
        </p>
      ) : null}
      {unavailableMessageCopy ? (
        <div className="chat-shell__notice chat-shell__notice--handoff">
          <span>{unavailableMessageCopy.availabilityLine}</span>
          <br />
          <span>
            {unavailableMessageCopy.retryLine}{" "}
            <a
              href="/contact"
              style={{
                color: "var(--text)",
                textDecoration: "underline",
                textUnderlineOffset: "3px",
              }}
            >
              {chatShellCopy.contactFormLinkLabel}
            </a>
            .
          </span>
        </div>
      ) : null}
      {warmupStatus === "error" ? (
        <p className="chat-shell__notice">
          {chatNoticeCopy.warmupUnavailable}
        </p>
      ) : null}
      {notice ? <p className="chat-shell__notice">{notice}</p> : null}

      <form className="chat-shell__form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="chat-message">
          {chatShellCopy.inputAriaLabel}
        </label>
        <textarea
          ref={messageInputRef}
          id="chat-message"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder={inputPlaceholder}
          maxLength={2000}
          rows={1}
          disabled={
            isThinking ||
            isEscalating ||
            isSendingHandoffMessage ||
            isClosingHandoff
          }
        />
        <button
          type="submit"
          aria-label={chatShellCopy.sendLabel}
          disabled={
            isThinking ||
            isEscalating ||
            isSendingHandoffMessage ||
            isClosingHandoff ||
            !input.trim()
          }
        >
          <span aria-hidden="true">{">"}</span>
        </button>
      </form>
    </section>
  );
}

function createStreamTextRenderer({
  signal,
  onUpdate,
}: StreamTextRendererOptions): StreamTextRenderer {
  let pendingText = "";
  let visibleText = "";
  let isCancelled = false;
  let isFinishing = false;
  let timerId: number | null = null;
  let finishResolver: (() => void) | null = null;

  function append(text: string) {
    if (isCancelled || !text) {
      return;
    }

    pendingText += text;
    scheduleTick();
  }

  function scheduleTick() {
    if (isCancelled || timerId !== null) {
      return;
    }
    if (!pendingText) {
      resolveIfFinished();
      return;
    }

    timerId = window.setTimeout(runTick, STREAM_RENDER_TICK_MS);
  }

  function runTick() {
    timerId = null;
    if (isCancelled) {
      resolveIfFinished();
      return;
    }

    const batchSize = nextStreamRenderBatchSize(pendingText.length, isFinishing);
    const nextText = pendingText.slice(0, batchSize);
    pendingText = pendingText.slice(batchSize);
    visibleText += nextText;
    onUpdate(visibleText);

    if (pendingText) {
      scheduleTick();
      return;
    }

    resolveIfFinished();
  }

  function finish() {
    isFinishing = true;
    if (!pendingText) {
      return Promise.resolve();
    }

    scheduleTick();
    return new Promise<void>((resolve) => {
      finishResolver = resolve;
    });
  }

  function flush() {
    if (isCancelled || !pendingText) {
      return;
    }

    if (timerId !== null) {
      window.clearTimeout(timerId);
      timerId = null;
    }
    visibleText += pendingText;
    pendingText = "";
    onUpdate(visibleText);
    resolveIfFinished();
  }

  function cancel() {
    isCancelled = true;
    pendingText = "";
    if (timerId !== null) {
      window.clearTimeout(timerId);
      timerId = null;
    }
    resolveIfFinished();
  }

  function resolveIfFinished() {
    if (pendingText || !finishResolver) {
      return;
    }

    finishResolver();
    finishResolver = null;
  }

  signal.addEventListener("abort", cancel, { once: true });

  return {
    append,
    cancel,
    finish,
    flush,
  };
}

function nextStreamRenderBatchSize(
  pendingLength: number,
  isFinishing: boolean,
): number {
  if (pendingLength >= STREAM_RENDER_LARGE_BACKLOG) {
    return STREAM_RENDER_FAST_CHARS;
  }
  if (pendingLength >= STREAM_RENDER_MEDIUM_BACKLOG) {
    return STREAM_RENDER_MEDIUM_CHARS;
  }
  if (isFinishing && pendingLength > STREAM_RENDER_MEDIUM_CHARS) {
    return STREAM_RENDER_MEDIUM_CHARS;
  }

  return STREAM_RENDER_BASE_CHARS;
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


function DelayedMessageSources({
  message,
}: Readonly<{
  message: Message;
}>) {
  const sourceCount = message.sources?.length ?? 0;
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    if (!sourceCount) {
      return;
    }

    const timeoutIds = Array.from({ length: sourceCount }, (_, index) => {
      return window.setTimeout(() => {
        setVisibleCount((currentCount) => Math.max(currentCount, index + 1));
      }, SOURCE_REVEAL_STEP_MS * (index + 1));
    });

    return () => {
      timeoutIds.forEach((timeoutId) => window.clearTimeout(timeoutId));
    };
  }, [sourceCount]);

  const visibleSources = message.sources?.slice(0, visibleCount) ?? [];

  if (!visibleSources.length) {
    return null;
  }

  return (
    <div className="message-sources" aria-label={chatShellCopy.sourceLabel}>
      {visibleSources.map((source) => (
        <span key={`${source.title}-${source.section || "document"}`}>
          {source.title}
          {source.section ? ` / ${source.section}` : ""}
        </span>
      ))}
    </div>
  );
}

function formatHandoffUnavailableMessage(message: string): {
  availabilityLine: string;
  retryLine: string;
} {
  const retryLine = chatHandoffCopy.unavailableRetryLine;
  const fallbackLine = DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE.replace(
    ` ${retryLine}`,
    "",
  );
  const trimmedMessage = message.trim() || DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE;
  const availabilityLine = trimmedMessage.replace(` ${retryLine}`, "").trim();

  return {
    availabilityLine: availabilityLine || fallbackLine,
    retryLine,
  };
}
