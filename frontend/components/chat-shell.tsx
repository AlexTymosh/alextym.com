"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ESCALATION_CONSENT_COPY,
  quickPrompts,
  thinkingMessages,
  warmupMessages,
} from "../content/chat";
import { useAnimatedLabel } from "../hooks/use-animated-label";
import { fetchJsonChatResponse, streamChatResponse } from "../lib/chat-api";
import {
  closeEscalationStream,
  normaliseHandoffState,
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
  isAbortError,
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
import type { HandoffState, Message, QuickPrompt } from "../types/chat";

export function ChatShell() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [warmupStatus, setWarmupStatus] = useState<
    "warming" | "ready" | "error"
  >("warming");
  const [isThinking, setIsThinking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [isEscalating, setIsEscalating] = useState(false);
  const [isSendingHandoffMessage, setIsSendingHandoffMessage] = useState(false);
  const [isClosingHandoff, setIsClosingHandoff] = useState(false);
  const [escalationSent, setEscalationSent] = useState(false);
  const [handoffId, setHandoffId] = useState<string | null>(null);
  const [handoffState, setHandoffState] = useState<HandoffState>("idle");
  const [handoffExpiresInSeconds, setHandoffExpiresInSeconds] = useState<
    number | null
  >(null);
  const [dismissedHandoffMessageCount, setDismissedHandoffMessageCount] =
    useState<number | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
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
      return "Alex is connected";
    }
    if (handoffState === "waiting_for_alex") {
      return "Waiting for Alex";
    }
    if (handoffState === "error") {
      return "Handoff reconnecting";
    }
    if (handoffState === "closed") {
      return "Handoff closed";
    }
    if (warmupStatus === "ready") {
      return "Ready";
    }
    if (warmupStatus === "error") {
      return "Warm-up unavailable";
    }
    return warmupLabel;
  }, [handoffState, warmupLabel, warmupStatus]);

  const inputPlaceholder = useMemo(() => {
    if (isHumanHandoffActive(handoffId, handoffState)) {
      return "Message Alex through this chat...";
    }
    if (handoffState === "closed") {
      return "Ask my assistant anything or request a new connection...";
    }
    return "Ask my assistant anything...";
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

  function resetChat() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    closeEscalationStream(escalationEventSourceRef);
    seenEscalationMessageIdsRef.current.clear();
    setInput("");
    setMessages([]);
    setIsThinking(false);
    setNotice(null);
    setIsEscalating(false);
    setIsSendingHandoffMessage(false);
    setIsClosingHandoff(false);
    setEscalationSent(false);
    setHandoffId(null);
    setHandoffState("idle");
    setHandoffExpiresInSeconds(null);
    setDismissedHandoffMessageCount(null);
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
    setDismissedHandoffMessageCount(null);

    try {
      await waitForScriptedResponse(abortController.signal);
      updateAssistantMessage(assistantId, {
        text: chooseScriptedResponse(prompt.responses),
      });
    } catch (error) {
      if (!isAbortError(error)) {
        updateAssistantMessage(assistantId, {
          text: "Something went wrong. Please try again later.",
          confidence: "low",
          notEnoughData: true,
        });
        setNotice("The assistant is temporarily unavailable.");
      }
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
      setIsThinking(false);
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

    if (isHandoffRequestText(trimmedInput)) {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: createMessageId("user"), role: "user", text: trimmedInput },
      ]);
      setInput("");
      setNotice(null);
      setDismissedHandoffMessageCount(null);
      return;
    }

    const assistantId = createMessageId("assistant");
    const history = buildChatHistory(messages);
    let streamedText = "";

    abortControllerRef.current?.abort();
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setMessages((currentMessages) => [
      ...currentMessages,
      { id: createMessageId("user"), role: "user", text: trimmedInput },
      { id: assistantId, role: "assistant", text: "" },
    ]);
    setInput("");
    setIsThinking(true);
    setNotice(null);
    setDismissedHandoffMessageCount(null);

    try {
      await streamChatResponse({
        message: trimmedInput,
        history,
        signal: abortController.signal,
        onToken: (token) => {
          streamedText += token;
          updateAssistantMessage(assistantId, { text: streamedText });
        },
        onSources: (sources) =>
          updateAssistantMessage(assistantId, { sources }),
        onDone: (done) =>
          updateAssistantMessage(assistantId, {
            confidence: done.confidence,
            notEnoughData: done.not_enough_data,
            handoffSuggested: done.handoff_suggested,
            handoffReason: done.handoff_reason ?? null,
          }),
      });
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }

      if (!streamedText) {
        try {
          const fallbackResponse = await fetchJsonChatResponse(
            trimmedInput,
            history,
            abortController.signal,
          );
          updateAssistantMessage(assistantId, {
            text: fallbackResponse.answer,
            sources: fallbackResponse.sources,
            confidence: fallbackResponse.confidence,
            notEnoughData: fallbackResponse.not_enough_data,
            handoffSuggested: fallbackResponse.handoff_suggested,
            handoffReason: fallbackResponse.handoff_reason ?? null,
          });
          setNotice(
            "Streaming was unavailable, so the JSON fallback was used.",
          );
        } catch (fallbackError) {
          if (!isAbortError(fallbackError)) {
            updateAssistantMessage(assistantId, {
              text: "Something went wrong. Please try again later.",
              confidence: "low",
              notEnoughData: true,
            });
            setNotice("The assistant is temporarily unavailable.");
          }
        }
      } else {
        setNotice("The streaming response ended before completion.");
      }
    } finally {
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
      setIsThinking(false);
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

    try {
      await submitEscalationMessage(handoffId, messageText);
      setMessages((currentMessages) => [
        ...currentMessages,
        { id: createMessageId("user"), role: "user", text: messageText },
      ]);
      setInput("");
      setDismissedHandoffMessageCount(null);
    } catch {
      setNotice(
        "Could not send this message to Alex right now. Please try again later.",
      );
    } finally {
      setIsSendingHandoffMessage(false);
    }
  }

  async function connectWithAlex() {
    if (isEscalating || isThinking || !messages.length) {
      return;
    }

    setIsEscalating(true);
    setNotice(null);

    try {
      const response = await submitEscalation(
        buildEscalationTranscript(messages),
      );
      const nextHandoffId = response.handoff_id || null;
      const nextState = normaliseHandoffState(response.state);

      setEscalationSent(true);
      setDismissedHandoffMessageCount(messages.length);
      setHandoffId(nextHandoffId);
      setHandoffExpiresInSeconds(response.expires_in_seconds ?? null);
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
            ? "Alex has been notified and can review this chat for context. " +
              "Keep this page open — any replies from Alex will appear here " +
              "automatically. You can continue with the AI assistant while " +
              "you wait."
            : "Alex has been notified and will be able to review this chat " +
              "for context. You can continue with the AI assistant while " +
              "you wait.",
        },
      ]);
    } catch {
      setNotice(
        "Could not connect with Alex right now. Please try again later.",
      );
    } finally {
      setIsEscalating(false);
    }
  }

  async function closeHandoff() {
    if (!handoffId || handoffState === "closed" || isClosingHandoff) {
      return;
    }

    setIsClosingHandoff(true);
    setNotice(null);

    try {
      await submitEscalationClose(handoffId);
      closeEscalationStream(escalationEventSourceRef);
      setHandoffState("closed");
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          text:
            "This handoff has been closed. New messages will go to " +
            "the AI assistant unless you request a new connection.",
        },
      ]);
    } catch {
      setNotice("Could not close this handoff right now. Please try again later.");
    } finally {
      setIsClosingHandoff(false);
    }
  }

  function continueWithAi() {
    setDismissedHandoffMessageCount(messages.length);
    setNotice(null);
  }

  function openEscalationStream(nextHandoffId: string) {
    closeEscalationStream(escalationEventSourceRef);

    const eventSource = new EventSource(
      `/api/escalations/${encodeURIComponent(nextHandoffId)}/stream`,
    );
    escalationEventSourceRef.current = eventSource;

    eventSource.addEventListener("meta", () => {
      setNotice(null);
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
    });

    eventSource.addEventListener("closed", () => {
      closeEscalationStream(escalationEventSourceRef);
      setHandoffState("closed");
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          text:
            "This handoff session has expired. You can continue with the " +
            "AI assistant or request a new connection with Alex.",
        },
      ]);
    });

    eventSource.addEventListener("error", () => {
      setHandoffState((currentState) =>
        currentState === "connected" ? "connected" : "error",
      );
      setNotice(
        "The live handoff connection is reconnecting. Please keep this page open.",
      );
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  return (
    <section className="chat-shell" aria-label="AI digital assistant">
      <div className="chat-shell__header">
        <div className="chat-shell__title">
          <span
            className={`status-dot status-dot--${warmupStatus}`}
            aria-hidden="true"
          />
          <div>
            <h1>Alex&apos;s AI Assistant</h1>
            <p>{statusLabel}</p>
          </div>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={resetChat}
          aria-label="Reset chat"
        >
          <span aria-hidden="true">R</span>
        </button>
      </div>

      <div className="chat-shell__body">
        {messages.length === 0 ? (
          <div className="chat-shell__empty">
            <div className="assistant-orb" aria-hidden="true">
              {"{ }"}
            </div>
            <h2>Hi, I&apos;m Alex&apos;s AI assistant.</h2>
            <p>
              Ask about Alex&apos;s public profile, work experience, automation
              projects, and availability.
            </p>
            <div className="prompt-list" aria-label="Quick prompts">
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
                  <div className="message__sender">Alex</div>
                ) : null}
                <div className="message__content">
                  {renderMessageText(
                    getRenderableMessageText(message, thinkingLabel),
                  )}
                </div>
                {message.role === "assistant" && message.sources?.length ? (
                  <div className="message-sources" aria-label="Sources">
                    {message.sources.map((source) => (
                      <span
                        key={`${source.title}-${source.section || "document"}`}
                      >
                        {source.title}
                        {source.section ? ` / ${source.section}` : ""}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>

      {shouldShowHandoffPrompt ? (
        <div
          className="message message--assistant"
          role="region"
          aria-label="Connect with Alex"
        >
          <div className="message__content">
            <p>
              <strong>Would you like to connect with Alex?</strong>
            </p>
            <p>{ESCALATION_CONSENT_COPY}</p>
          </div>
          <div className="prompt-list" aria-label="Handoff actions">
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
                {isEscalating ? "Connecting..." : "Connect me with Alex"}
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
              <span>Continue with AI</span>
            </button>
          </div>
        </div>
      ) : null}

      {isHumanHandoffActive(handoffId, handoffState) ? (
        <div
          className="message message--assistant"
          role="region"
          aria-label="Active handoff"
        >
          <div className="message__content">
            <p>
              <strong>Human handoff is active.</strong>
            </p>
            <p>Messages you send now go to Alex, not to the AI assistant.</p>
          </div>
          <div className="prompt-list" aria-label="Active handoff actions">
            <button
              type="button"
              className="prompt-button"
              onClick={() => void closeHandoff()}
              disabled={isClosingHandoff}
            >
              <span className="prompt-button__icon" aria-hidden="true">
                {">"}
              </span>
              <span>{isClosingHandoff ? "Closing..." : "End handoff"}</span>
            </button>
          </div>
        </div>
      ) : null}

      {handoffId ? (
        <p className="chat-shell__notice">
          {handoffStatusCopy(handoffState, handoffExpiresInSeconds)}
        </p>
      ) : null}
      {warmupStatus === "error" ? (
        <p className="chat-shell__notice">
          Backend warm-up is unavailable in this environment. The assistant may
          still respond.
        </p>
      ) : null}
      {notice ? <p className="chat-shell__notice">{notice}</p> : null}

      <form className="chat-shell__form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="chat-message">
          Ask Alex&apos;s AI assistant
        </label>
        <input
          id="chat-message"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={inputPlaceholder}
          maxLength={2000}
          disabled={
            isThinking ||
            isEscalating ||
            isSendingHandoffMessage ||
            isClosingHandoff
          }
        />
        <button
          type="submit"
          aria-label="Send message"
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

