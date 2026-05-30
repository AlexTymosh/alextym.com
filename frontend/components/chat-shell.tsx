"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

type Confidence = "low" | "medium" | "high";
type MessageRole = "user" | "assistant" | "alex";
type HandoffState =
  | "idle"
  | "waiting_for_alex"
  | "connected"
  | "closed"
  | "error";

type HandoffReason = "insufficient_data" | "private_data";

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
  handoff_suggested?: boolean;
  handoff_reason?: HandoffReason | null;
};

type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type EscalationTranscriptMessage = {
  role: "user" | "assistant";
  content: string;
};

type EscalationResponse = {
  status: string;
  handoff_id?: string | null;
  state?: string | null;
  expires_in_seconds?: number | null;
};

type EscalationMessageResponse = {
  status: string;
};

type EscalationCloseResponse = {
  status: string;
  state: string;
};

type EscalationStreamMessage = {
  id?: string;
  role?: string;
  content?: string;
  created_at?: string;
};

type Message = {
  id: string;
  role: MessageRole;
  text: string;
  sources?: ChatSource[];
  confidence?: Confidence;
  notEnoughData?: boolean;
  handoffSuggested?: boolean;
  handoffReason?: HandoffReason | null;
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
const ESCALATION_TRANSCRIPT_LIMIT = 20;
const ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS = 2000;
const ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS = 8000;
const ESCALATION_CONSENT_COPY =
  "If you connect with Alex, this chat history will be shared with him so he can " +
  "understand the context. No email or phone number will be shared unless you " +
  "type it yourself.";

const HANDOFF_REQUEST_PATTERNS = [
  /\bconnect\s+(me\s+)?(with|to)\s+alex\b/i,
  /\bcan\s+you\s+connect\s+me\s+(with|to)\s+alex\b/i,
  new RegExp(
    String.raw`\bi\s+(want|would\s+like|need)\s+(to\s+)?` +
      String.raw`(talk|speak|chat)\s+(to|with)\s+alex\b`,
    "i",
  ),
  /\b(talk|speak|chat)\s+(to|with)\s+alex\b/i,
  /\bcan\s+alex\s+(contact|call|message|email|reach)\s+me\b/i,
  new RegExp(
    String.raw`\bget\s+alex\s+(to\s+)?` +
      String.raw`(contact|call|message|email|reply\s+to)\s+me\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bplease\s+(connect|put)\s+me\s+` +
      String.raw`(through\s+)?(to\s+)?alex\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bi\s+(want|would\s+like|need)\s+(to\s+)?` +
      String.raw`(talk|speak|chat)\s+(to|with)\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b(talk|speak|chat)\s+(to|with)\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b(connect|handoff|escalate)\s+(me\s+)?(to\s+)?` +
      String.raw`(a\s+)?(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bconnect\s+me\s+with\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bi\s+need\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bcan\s+i\s+(talk|speak|chat)\s+(to|with)\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  /^\s*(human|person|real\s+person|agent|representative|operator)\s*[.!?]*\s*$/i,
] as const;

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
                className={
                  `message message--${
                    message.role === "alex" ? "assistant" : message.role
                  }`
                }
              >
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

  const currentMessage = active
    ? messages[messageIndex % messages.length] || messages[0]
    : messages[0];
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
  return (
    responses[Math.floor(Math.random() * responses.length)] ||
    responses[0] ||
    ""
  );
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
  onDone: (done: {
    confidence: Confidence;
    not_enough_data: boolean;
    handoff_suggested?: boolean;
    handoff_reason?: HandoffReason | null;
  }) => void;
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

async function submitEscalation(
  transcript: EscalationTranscriptMessage[],
): Promise<EscalationResponse> {
  const response = await fetch("/api/escalations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      consent_accepted: true,
      reason: "user_requested_human",
      transcript,
      company_website: "",
    }),
  });

  if (!response.ok) {
    throw new Error("Escalation request unavailable.");
  }

  return (await response.json()) as EscalationResponse;
}

async function submitEscalationMessage(
  handoffId: string,
  content: string,
): Promise<EscalationMessageResponse> {
  const response = await fetch(
    `/api/escalations/${encodeURIComponent(handoffId)}/messages`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        content,
        company_website: "",
      }),
    },
  );

  if (!response.ok) {
    throw new Error("Escalation message request unavailable.");
  }

  return (await response.json()) as EscalationMessageResponse;
}

async function submitEscalationClose(
  handoffId: string,
): Promise<EscalationCloseResponse> {
  const response = await fetch(
    `/api/escalations/${encodeURIComponent(handoffId)}/close`,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error("Escalation close request unavailable.");
  }

  return (await response.json()) as EscalationCloseResponse;
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
    onDone: (done: {
      confidence: Confidence;
      not_enough_data: boolean;
      handoff_suggested?: boolean;
      handoff_reason?: HandoffReason | null;
    }) => void;
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
      handoff_suggested?: boolean;
      handoff_reason?: HandoffReason | null;
    };
    handlers.onDone({
      confidence: payload.confidence || "low",
      not_enough_data: payload.not_enough_data ?? true,
      handoff_suggested: payload.handoff_suggested,
      handoff_reason: payload.handoff_reason ?? null,
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
    if (message.role === "alex") {
      continue;
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

function buildEscalationTranscript(
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

function parseEscalationStreamMessage(
  event: Event,
): { id: string; content: string } | null {
  if (!(event instanceof MessageEvent)) {
    return null;
  }

  const payload = safeParseJson(event.data) as EscalationStreamMessage | null;
  if (!payload || payload.role !== "alex") {
    return null;
  }

  const content =
    typeof payload.content === "string" ? payload.content.trim() : "";
  if (!content) {
    return null;
  }

  return {
    id: event.lastEventId || payload.id || createMessageId("alex"),
    content,
  };
}

function safeParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function normaliseHandoffState(state: string | null | undefined): HandoffState {
  if (state === "connected") {
    return "connected";
  }
  if (state === "closed") {
    return "closed";
  }
  return "waiting_for_alex";
}

function closeEscalationStream(eventSourceRef: {
  current: EventSource | null;
}) {
  eventSourceRef.current?.close();
  eventSourceRef.current = null;
}

function isHumanHandoffActive(
  handoffId: string | null,
  state: HandoffState,
): boolean {
  return (
    Boolean(handoffId) &&
    ["waiting_for_alex", "connected", "error"].includes(state)
  );
}

function handoffStatusCopy(
  state: HandoffState,
  expiresInSeconds: number | null,
): string {
  const expirySuffix = expiresInSeconds
    ? ` This session stays open for about ${formatDuration(expiresInSeconds)}.`
    : "";

  if (state === "connected") {
    return (
      "Alex has replied in this chat. New messages you send here will go " +
      `to Alex.${expirySuffix}`
    );
  }
  if (state === "closed") {
    return (
      "This handoff session has closed. You can continue with the AI " +
      "assistant or request a new connection."
    );
  }
  if (state === "error") {
    return "The live handoff connection is reconnecting. Keep this page open.";
  }
  return (
    "Waiting for Alex. His replies will appear here automatically, and " +
    `new messages you send here will go to Alex.${expirySuffix}`
  );
}

function formatDuration(totalSeconds: number): string {
  const minutes = Math.max(1, Math.round(totalSeconds / 60));
  if (minutes < 60) {
    return `${minutes} minutes`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours} ${hours === 1 ? "hour" : "hours"}`;
}

function getRenderableMessageText(
  message: Message,
  thinkingLabel: string,
): string {
  if (message.text) {
    return message.role === "alex" ? `Alex:\n\n${message.text}` : message.text;
  }

  return message.role === "assistant" ? thinkingLabel : "";
}

function shouldAssistantSuggestHandoff(message: Message): boolean {
  if (typeof message.handoffSuggested === "boolean") {
    return message.handoffSuggested;
  }

  return Boolean(message.notEnoughData || isHandoffInvitationText(message.text));
}

function isHandoffInvitationText(text: string): boolean {
  const normalizedText = text.toLowerCase();
  return (
    normalizedText.includes("would you like me to connect him directly") ||
    normalizedText.includes("connect with alex") ||
    normalizedText.includes("connect me with alex")
  );
}

function isHandoffRequestText(text: string): boolean {
  const compactText = text.replace(/\s+/g, " ").trim();
  return HANDOFF_REQUEST_PATTERNS.some((pattern) => pattern.test(compactText));
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
      nodes.push(
        <span
          key={`break-${index}`}
          className="message__break"
          aria-hidden="true"
        />,
      );
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
