"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Confidence = "low" | "medium" | "high";

type ChatSource = {
  title: string;
  section?: string | null;
  confidence: Confidence;
};

type ChatResponse = {
  answer: string;
  sources: ChatSource[];
  confidence: Confidence;
  not_enough_data: boolean;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
  confidence?: Confidence;
  notEnoughData?: boolean;
};

type SseEvent = {
  event: string;
  data: string;
};

const quickPrompts = [
  "Summarize Alex's professional profile.",
  "Tell me about Alex's FastAPI and backend experience.",
  "Tell me about Alex's AI-assisted development and RAG-based systems.",
];

export function ChatShell() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [warmupStatus, setWarmupStatus] = useState<"warming" | "ready" | "error">("warming");
  const [isThinking, setIsThinking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

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
    };
  }, []);

  const statusLabel = useMemo(() => {
    if (warmupStatus === "ready") {
      return "Ready";
    }

    if (warmupStatus === "error") {
      return "Warm-up unavailable";
    }

    return "Warming up";
  }, [warmupStatus]);

  function resetChat() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setInput("");
    setMessages([]);
    setIsThinking(false);
    setNotice(null);
  }

  async function sendMessage(messageText: string) {
    const trimmedInput = messageText.trim();
    if (!trimmedInput) {
      return;
    }
    if (isThinking) {
      return;
    }

    const assistantId = createMessageId("assistant");
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

    try {
      await streamChatResponse({
        message: trimmedInput,
        signal: abortController.signal,
        onToken: (token) => {
          streamedText += token;
          updateAssistantMessage(assistantId, { text: streamedText });
        },
        onSources: (sources) => updateAssistantMessage(assistantId, { sources }),
        onDone: (done) =>
          updateAssistantMessage(assistantId, {
            confidence: done.confidence,
            notEnoughData: done.not_enough_data,
          }),
      });
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }

      if (!streamedText) {
        try {
          const fallbackResponse = await fetchJsonChatResponse(trimmedInput, abortController.signal);
          updateAssistantMessage(assistantId, {
            text: fallbackResponse.answer,
            sources: fallbackResponse.sources,
            confidence: fallbackResponse.confidence,
            notEnoughData: fallbackResponse.not_enough_data,
          });
          setNotice("Streaming was unavailable, so the JSON fallback was used.");
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  return (
    <section className="chat-shell" aria-label="AI digital assistant">
      <div className="chat-shell__header">
        <div className="chat-shell__title">
          <span className={`status-dot status-dot--${warmupStatus}`} aria-hidden="true" />
          <div>
            <h1>AI Digital Twin</h1>
            <p>{statusLabel}</p>
          </div>
        </div>
        <button type="button" className="icon-button" onClick={resetChat} aria-label="Reset chat">
          <span aria-hidden="true">R</span>
        </button>
      </div>

      <div className="chat-shell__body">
        {messages.length === 0 ? (
          <div className="chat-shell__empty">
            <div className="assistant-orb" aria-hidden="true">
              {"{ }"}
            </div>
            <h2>Hi, I&apos;m Alex&apos;s digital assistant.</h2>
            <p>
              This AI is augmented by Alex&apos;s work and experiences. Ask about RAG projects or
              AI automation workflows.
            </p>
            <div className="prompt-list" aria-label="Quick prompts">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="prompt-button"
                  onClick={() => void sendMessage(prompt)}
                  disabled={isThinking}
                >
                  <span className="prompt-button__icon" aria-hidden="true">
                    {">"}
                  </span>
                  <span>{prompt}</span>
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
                <div className="message__content">
                  {renderMessageText(
                    message.text || (message.role === "assistant" ? "Thinking..." : ""),
                  )}
                </div>
                {message.role === "assistant" && message.sources?.length ? (
                  <div className="message-sources" aria-label="Sources">
                    {message.sources.map((source) => (
                      <span key={`${source.title}-${source.section || "document"}`}>
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

      {warmupStatus === "error" ? (
        <p className="chat-shell__notice">
          Backend warm-up is unavailable in this environment. The assistant may still respond.
        </p>
      ) : null}
      {notice ? <p className="chat-shell__notice">{notice}</p> : null}

      <form className="chat-shell__form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="chat-message">
          Ask Alex&apos;s digital assistant
        </label>
        <input
          id="chat-message"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask my assistant anything..."
          maxLength={2000}
          disabled={isThinking}
        />
        <button type="submit" aria-label="Send message" disabled={isThinking || !input.trim()}>
          <span aria-hidden="true">{">"}</span>
        </button>
      </form>
    </section>
  );
}

async function streamChatResponse({
  message,
  signal,
  onToken,
  onSources,
  onDone,
}: {
  message: string;
  signal: AbortSignal;
  onToken: (token: string) => void;
  onSources: (sources: ChatSource[]) => void;
  onDone: (done: { confidence: Confidence; not_enough_data: boolean }) => void;
}) {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error("Streaming response unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || "";

    for (const part of parts) {
      handleSseEvent(parseSseEvent(part), { onToken, onSources, onDone });
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    handleSseEvent(parseSseEvent(buffer), { onToken, onSources, onDone });
  }
}

async function fetchJsonChatResponse(message: string, signal: AbortSignal): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok) {
    throw new Error("JSON fallback response unavailable.");
  }

  return (await response.json()) as ChatResponse;
}

function parseSseEvent(rawEvent: string): SseEvent | null {
  const lines = rawEvent.split(/\r?\n/);
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!dataLines.length) {
    return null;
  }

  return { event, data: dataLines.join("\n") };
}

function handleSseEvent(
  sseEvent: SseEvent | null,
  handlers: {
    onToken: (token: string) => void;
    onSources: (sources: ChatSource[]) => void;
    onDone: (done: { confidence: Confidence; not_enough_data: boolean }) => void;
  },
) {
  if (!sseEvent) {
    return;
  }

  if (sseEvent.event === "token") {
    const payload = JSON.parse(sseEvent.data) as { text?: string };
    handlers.onToken(payload.text || "");
    return;
  }

  if (sseEvent.event === "sources") {
    const payload = JSON.parse(sseEvent.data) as { sources?: ChatSource[] };
    handlers.onSources(payload.sources || []);
    return;
  }

  if (sseEvent.event === "done") {
    const payload = JSON.parse(sseEvent.data) as {
      confidence?: Confidence;
      not_enough_data?: boolean;
    };
    handlers.onDone({
      confidence: payload.confidence || "low",
      not_enough_data: payload.not_enough_data ?? true,
    });
    return;
  }

  if (sseEvent.event === "error") {
    throw new Error("Streaming error event received.");
  }
}

function createMessageId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}`;
}

function renderMessageText(text: string) {
  const normalizedText = text
    .replace(/:\s+[-*]\s+/g, ":\n- ")
    .replace(/\s+[-*]\s+(?=[A-ZА-ЯЁ0-9])/g, "\n- ");
  const lines = normalizedText.split(/\r?\n/);
  const nodes: JSX.Element[] = [];
  let listItems: string[] = [];

  function flushList(key: string) {
    if (!listItems.length) {
      return;
    }

    nodes.push(
      <ul key={`list-${key}`}>
        {listItems.map((item, index) => (
          <li key={`${key}-${index}`}>{item}</li>
        ))}
      </ul>,
    );
    listItems = [];
  }

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();
    const bulletMatch = trimmedLine.match(/^[-*]\s+(.+)$/);

    if (bulletMatch) {
      listItems.push(bulletMatch[1]);
      return;
    }

    flushList(String(index));

    if (!trimmedLine) {
      nodes.push(<span key={`break-${index}`} className="message__break" aria-hidden="true" />);
      return;
    }

    nodes.push(<p key={`paragraph-${index}`}>{trimmedLine}</p>);
  });

  flushList("end");

  return nodes.length ? nodes : <p>{normalizedText}</p>;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
