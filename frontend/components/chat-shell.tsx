"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

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

type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
  confidence?: Confidence;
  notEnoughData?: boolean;
};

type QuickPrompt = {
  label: string;
  responses: readonly string[];
};

type SseEvent = {
  event: string;
  data: string;
};

const quickPrompts: readonly QuickPrompt[] = [
  {
    label: "Give me your 1-minute intro.",
    responses: [
      `Alex builds practical automation for business workflows, APIs, ERP systems, reporting, and dashboards.

His automation background goes back to the 2000s:
- Excel macros while working as a credit broker;
- MySQL for company operations in 2018;
- Bitrix24 ERP during the 2020 remote-work shift.

After the war in Ukraine forced his move to the UK in 2022, he focused on AI-assisted engineering, Python automation, and API integrations.

In 2024, he delivered an Odoo Enterprise API integration that reduced one employee's workload by 68%.

He also holds an MBA with honours and has a strong analytical background.

Would you like to know more about his latest work experience?`,
      `Alex combines long-term business automation experience with newer AI-assisted software development.

He started with Excel automation in the 2000s, then moved business operations into MySQL in 2018 and Bitrix24 ERP in 2020.

After the war in Ukraine forced his move to the UK in 2022, he focused more deeply on Python, AI engineering, APIs, and workflow automation.

His 2024 Odoo Enterprise API project reduced one employee's workload by 68%.

He also holds an MBA with honours and is strong in analytics, reporting, and dashboards.

Would you like a short overview of his most recent role?`,
      `Alex focuses on automation, API integrations, ERP workflows, reporting, and operational dashboards.

His practical automation path includes:
- Excel macros in the 2000s;
- moving company processes to MySQL in 2018;
- implementing Bitrix24 ERP in 2020;
- building API-based workflow automation in the UK.

After the war in Ukraine forced his move to the UK in 2022, he shifted his focus towards AI-assisted engineering and Python automation.

In 2024, he delivered an Odoo Enterprise integration that reduced one employee's workload by 68%.

Would you like the key facts from his latest work experience?`,
    ],
  },
  {
    label: "Give me a short overview of his work experience.",
    responses: [
      `Alex's career started in finance and operations:
- assistant accountant;
- economist and senior economist;
- deputy branch manager in banking;
- credit broker;
- managing director of a recruitment company.

He later helped grow that recruitment company into a regional leader.

After the war in Ukraine forced his move to the UK in late 2022, he focused more deeply on Python, AI-assisted analytics, and automation.

His first UK role was at Hydrosphere UK, where he worked as an Automation Engineer.

Would you like the key facts about his professional achievements?`,
      `Alex has a mixed business and software automation background.

His work experience includes:
- finance and accounting support;
- economist and senior economist roles;
- banking management;
- credit brokerage;
- managing a recruitment company that grew into a regional leader.

After the war in Ukraine forced his relocation to the UK in late 2022, he focused on Python, AI-assisted analytics, and workflow automation.

His first UK position was Automation Engineer at Hydrosphere UK.

Would you like a concise list of his strongest achievements?`,
      `Alex's work experience developed from finance and banking into business leadership and automation.

His earlier roles included:
- assistant accountant;
- economist and senior economist;
- deputy bank branch manager;
- credit broker;
- managing director of a recruitment company.

That recruitment company later became a regional leader.

After the war in Ukraine forced his move to the UK in 2022, he focused on Python, AI-assisted analytics, and automation.

His first UK role was Automation Engineer at Hydrosphere UK.

Would you like a summary of the most relevant achievements?`,
    ],
  },
  {
    label: "When is Alex ready to start work?",
    responses: [
      `Alex is currently freelancing, so he should usually be available relatively quickly.

I do not have access to his calendar, so the exact start date should be confirmed with him directly.

Would you like me to connect him directly?

Your details will not be passed to him at this stage, and he will not see your phone number or email unless you choose to share them.`,
      `Alex is doing freelance work, so his availability is likely to be relatively flexible.

I cannot check his calendar, so the safest answer is to ask him directly about the exact start date.

Would you like me to connect him directly?

Your contact details will not be shared with him at this stage unless you decide to provide them.`,
      `Alex should be able to discuss availability fairly quickly because he is currently freelancing.

I am not connected to his calendar, so I cannot confirm an exact start date here.

Would you like me to connect him directly?

He will not receive your phone number or email from this chat unless you choose to share those details.`,
    ],
  },
];

const warmupMessages = [
  "Give me a second, I’m getting ready",
  "Reviewing Alex’s public profile",
  "Checking project notes",
  "Preparing a clear answer",
] as const;

const thinkingMessages = [
  "Thinking",
  "Looking through Alex’s documents",
  "Preparing the answer",
] as const;

const CHAT_HISTORY_LIMIT = 8;
const CHAT_HISTORY_ITEM_MAX_CHARS = 1000;
const CHAT_HISTORY_TOTAL_MAX_CHARS = 6000;
const SCRIPTED_RESPONSE_DELAY_MS = 3000;

export function ChatShell() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [warmupStatus, setWarmupStatus] = useState<"warming" | "ready" | "error">("warming");
  const [isThinking, setIsThinking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const warmupLabel = useAnimatedLabel(warmupStatus === "warming", warmupMessages);
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
    };
  }, []);

  const statusLabel = useMemo(() => {
    if (warmupStatus === "ready") {
      return "Ready";
    }

    if (warmupStatus === "error") {
      return "Warm-up unavailable";
    }

    return warmupLabel;
  }, [warmupLabel, warmupStatus]);

  function resetChat() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setInput("");
    setMessages([]);
    setIsThinking(false);
    setNotice(null);
  }

  async function sendScriptedResponse(prompt: QuickPrompt) {
    if (isThinking) {
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

    try {
      await waitForScriptedResponse(abortController.signal);
      updateAssistantMessage(assistantId, { text: chooseScriptedResponse(prompt.responses) });
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
    if (isThinking) {
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

    try {
      await streamChatResponse({
        message: trimmedInput,
        history,
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
            <h1>Alex&apos;s AI Assistant</h1>
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
            <h2>Hi, I&apos;m Alex&apos;s AI assistant.</h2>
            <p>
              Ask about Alex&apos;s public profile, work experience, automation projects, and
              availability.
            </p>
            <div className="prompt-list" aria-label="Quick prompts">
              {quickPrompts.map((prompt) => (
                <button
                  key={prompt.label}
                  type="button"
                  className="prompt-button"
                  onClick={() => void sendScriptedResponse(prompt)}
                  disabled={isThinking}
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
                <div className="message__content">
                  {renderMessageText(
                    message.text || (message.role === "assistant" ? thinkingLabel : ""),
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
          Ask Alex&apos;s AI assistant
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

function useAnimatedLabel(
  active: boolean,
  messages: readonly string[],
  messageIntervalMs = 1800,
  dotIntervalMs = 500,
): string {
  const [messageIndex, setMessageIndex] = useState(0);
  const [dotCount, setDotCount] = useState(1);

  useEffect(() => {
    if (!active) {
      return;
    }

    const dotIntervalId = window.setInterval(() => {
      setDotCount((current) => (current >= 3 ? 1 : current + 1));
    }, dotIntervalMs);

    const messageIntervalId = window.setInterval(() => {
      setMessageIndex((current) => (current + 1) % messages.length);
    }, messageIntervalMs);

    return () => {
      window.clearInterval(dotIntervalId);
      window.clearInterval(messageIntervalId);
    };
  }, [active, dotIntervalMs, messageIntervalMs, messages]);

  const currentMessage = active ? messages[messageIndex % messages.length] || messages[0] : messages[0];
  const currentDotCount = active ? dotCount : 1;

  return `${currentMessage}${".".repeat(currentDotCount)}`;
}

async function waitForScriptedResponse(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Request aborted", "AbortError"));
      return;
    }

    const handleAbort = () => {
      window.clearTimeout(timeoutId);
      reject(new DOMException("Request aborted", "AbortError"));
    };

    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", handleAbort);
      resolve();
    }, SCRIPTED_RESPONSE_DELAY_MS);

    signal.addEventListener("abort", handleAbort, { once: true });
  });
}

function chooseScriptedResponse(responses: readonly string[]): string {
  return responses[Math.floor(Math.random() * responses.length)] || responses[0] || "";
}

async function streamChatResponse({
  message,
  history,
  signal,
  onToken,
  onSources,
  onDone,
}: {
  message: string;
  history: ChatHistoryMessage[];
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
    body: JSON.stringify({ message, history }),
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

async function fetchJsonChatResponse(
  message: string,
  history: ChatHistoryMessage[],
  signal: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ message, history }),
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

function buildChatHistory(messages: Message[]): ChatHistoryMessage[] {
  const history: ChatHistoryMessage[] = [];
  let totalChars = 0;

  for (const message of [...messages].reverse()) {
    if (history.length >= CHAT_HISTORY_LIMIT) {
      break;
    }

    const content = compactHistoryContent(message.text);
    if (!content) {
      continue;
    }

    if (totalChars + content.length > CHAT_HISTORY_TOTAL_MAX_CHARS) {
      break;
    }

    history.unshift({ role: message.role, content });
    totalChars += content.length;
  }

  return history;
}

function compactHistoryContent(text: string): string {
  const compactText = text.replace(/\s+/g, " ").trim();
  return compactText.slice(0, CHAT_HISTORY_ITEM_MAX_CHARS);
}

function renderMessageText(text: string) {
  const normalizedText = text
    .replace(/:\s+[-*]\s+/g, ":\n- ")
    .replace(/\s+[-*]\s+(?=[A-ZА-ЯЁ0-9])/g, "\n- ");
  const lines = normalizedText.split(/\r?\n/);
  const nodes: ReactNode[] = [];
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
