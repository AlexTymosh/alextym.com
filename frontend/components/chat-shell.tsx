"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Message = {
  role: "user" | "assistant";
  text: string;
};

const quickPrompts = [
  "Give me your 30-second intro.",
  "Tell me about your recent projects.",
  "Tell me about your RAG work",
];

export function ChatShell() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [warmupStatus, setWarmupStatus] = useState<"warming" | "ready" | "error">("warming");
  const [isThinking, setIsThinking] = useState(false);

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
    setInput("");
    setMessages([]);
    setIsThinking(false);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedInput = input.trim();

    if (!trimmedInput) {
      return;
    }

    setMessages((currentMessages) => [...currentMessages, { role: "user", text: trimmedInput }]);
    setInput("");
    setIsThinking(true);

    window.setTimeout(() => {
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          text: "This is a Stage 2 UI placeholder. The production chat service, streaming, and RAG answers will be connected in the next backend stages.",
        },
      ]);
      setIsThinking(false);
    }, 350);
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
                  onClick={() => setInput(prompt)}
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
              <div key={`${message.role}-${index}`} className={`message message--${message.role}`}>
                <span>{message.text}</span>
              </div>
            ))}
            {isThinking ? <div className="message message--assistant">Preparing mock reply...</div> : null}
          </div>
        )}
      </div>

      {warmupStatus === "error" ? (
        <p className="chat-shell__notice">
          Backend warm-up is unavailable in this environment. The UI placeholder remains usable.
        </p>
      ) : null}

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
        />
        <button type="submit" aria-label="Send message">
          <span aria-hidden="true">{">"}</span>
        </button>
      </form>
    </section>
  );
}
