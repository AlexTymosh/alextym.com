"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { useChatController } from "../hooks/use-chat-controller";
import {
  getRenderableMessageText,
  handoffStatusCopy,
  renderMessageText,
} from "../lib/chat-formatting";
import type { Message } from "../types/chat";

const DEFAULT_HANDOFF_UNAVAILABLE_MESSAGE =
  chatHandoffCopy.defaultUnavailableMessage;

const SOURCE_REVEAL_STEP_MS = 180;

export function ChatShell() {
  const chatBodyRef = useRef<HTMLDivElement | null>(null);
  const messageInputRef = useRef<HTMLTextAreaElement | null>(null);

  const focusMessageInputSoon = useCallback(() => {
    window.setTimeout(() => {
      messageInputRef.current?.focus();
    }, 0);
  }, []);

  const {
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
    isSubmitDisabled,
    isThinking,
    messages,
    notice,
    resetChat,
    sendScriptedResponse,
    setInput,
    shouldShowHandoffPrompt,
    warmupStatus,
  } = useChatController({
    focusMessageInputSoon,
  });

  const warmupLabel = useAnimatedLabel(
    warmupStatus === "warming",
    warmupMessages,
  );
  const thinkingLabel = useAnimatedLabel(isThinking, thinkingMessages);

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

  const handoffStatusText = useMemo(() => {
    return handoffId ? handoffStatusCopy(handoffState) : null;
  }, [handoffId, handoffState]);

  const unavailableMessageCopy = useMemo(() => {
    if (!handoffUnavailableMessage) {
      return null;
    }
    return formatHandoffUnavailableMessage(handoffUnavailableMessage);
  }, [handoffUnavailableMessage]);

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
                  disabled={isInputDisabled}
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

      {hasActiveHandoff ? (
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
          disabled={isInputDisabled}
        />
        <button
          type="submit"
          aria-label={chatShellCopy.sendLabel}
          disabled={isSubmitDisabled}
        >
          <span aria-hidden="true">{">"}</span>
        </button>
      </form>
    </section>
  );
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
