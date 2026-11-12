import { expect, test } from "@playwright/test";

import { chatNoticeCopy } from "../content/chat";
import { ChatStreamError } from "../lib/chat-api";
import {
  runChatResponseFlow,
  type ChatResponseFlowTransport,
} from "../lib/chat-response-flow";
import type { StreamTextRenderer } from "../lib/stream-text-renderer";
import type { AssistantMessage } from "../types/chat";

type Patch = Partial<Omit<AssistantMessage, "id" | "role">>;

function setup() {
  const operations: string[] = [];
  const patches: Patch[] = [];
  const notices: string[] = [];
  const controller = new AbortController();
  let visible = "";
  const renderer: StreamTextRenderer = {
    append: (text) => { visible += text; operations.push(`append:${text}`); },
    finish: async () => { operations.push("finish"); },
    flush: () => { operations.push("flush"); },
    cancel: () => { operations.push("cancel"); },
  };
  const options = {
    message: "Which technology?",
    history: [{ role: "user" as const, content: "Previous question" }],
    signal: controller.signal,
    renderer,
    onAssistantPatch: (patch: Patch) => { patches.push(patch); operations.push("patch"); },
    onNotice: (notice: string) => { notices.push(notice); },
  };
  return { controller, operations, patches, notices, options, visible: () => visible };
}

function transport(
  stream: ChatResponseFlowTransport["stream"],
  fetchJson: ChatResponseFlowTransport["fetchJson"] = async () => {
    throw new Error("Unexpected JSON request");
  },
): ChatResponseFlowTransport {
  return { stream, fetchJson };
}

test("applies done metadata immediately, and sources only after render completes", async () => {
  const h = setup();
  const source = { title: "Portfolio", confidence: "high" as const };
  await runChatResponseFlow(h.options, transport(async ({ onToken, onSources, onDone }) => {
    onToken("A");
    onToken("B");
    onSources([source]);
    onDone({
      confidence: "high", not_enough_data: false, retrieval_status: "success",
      handoff_suggested: false, handoff_reason: null,
    });
  }));
  expect(h.visible()).toBe("AB");
  expect(h.patches).toEqual([
    {
      confidence: "high", notEnoughData: false, retrievalStatus: "success",
      handoffSuggested: false, handoffReason: null,
      languageUnsupported: undefined, userRequestedHuman: undefined,
    },
    { sources: [source] },
  ]);
  expect(h.operations).toEqual(["append:A", "append:B", "patch", "finish", "patch", "cancel"]);
  expect(h.notices).toEqual([]);
});

test("does not fall back to JSON after a backend SSE error", async () => {
  const h = setup();
  let fallbackCalled = false;
  await runChatResponseFlow(h.options, transport(
    async () => { throw new ChatStreamError("backend_error", "Safe message"); },
    async () => { fallbackCalled = true; throw new Error("Not expected"); },
  ));
  expect(fallbackCalled).toBe(false);
  expect(h.patches).toEqual([{
    text: "Safe message", confidence: "low", notEnoughData: false,
    handoffSuggested: false, handoffReason: null,
  }]);
  expect(h.notices).toEqual([chatNoticeCopy.assistantUnavailable]);
  expect(h.operations).toEqual(["flush", "patch", "cancel"]);
});

test("preserves partial streamed content instead of replacing it with JSON", async () => {
  const h = setup();
  let fallbackCalled = false;
  await runChatResponseFlow(h.options, transport(
    async ({ onToken }) => {
      onToken("partial response");
      throw new ChatStreamError("incomplete", "stream ended");
    },
    async () => { fallbackCalled = true; throw new Error("Not expected"); },
  ));
  expect(h.visible()).toBe("partial response");
  expect(fallbackCalled).toBe(false);
  expect(h.patches).toEqual([]);
  expect(h.notices).toEqual([chatNoticeCopy.streamingEndedEarly]);
  expect(h.operations).toEqual(["append:partial response", "flush", "cancel"]);
});

test("uses JSON fallback only when no SSE tokens were received", async () => {
  const h = setup();
  await runChatResponseFlow(h.options, transport(
    async () => { throw new ChatStreamError("unavailable", "No stream"); },
    async () => ({
      answer: "Fallback answer", sources: [], confidence: "medium",
      not_enough_data: false, retrieval_status: "success",
      handoff_suggested: true, handoff_reason: "insufficient_data",
    }),
  ));
  expect(h.visible()).toBe("Fallback answer");
  expect(h.patches).toEqual([{
    sources: [], confidence: "medium", notEnoughData: false,
    retrievalStatus: "success", handoffSuggested: true,
    handoffReason: "insufficient_data", languageUnsupported: undefined,
    userRequestedHuman: undefined,
  }]);
  expect(h.notices).toEqual([chatNoticeCopy.streamingFallbackUsed]);
  expect(h.operations).toEqual(["append:Fallback answer", "finish", "patch", "cancel"]);
});

test("preserves existing user-facing error when JSON fallback fails", async () => {
  const h = setup();
  await runChatResponseFlow(h.options, transport(
    async () => { throw new Error("Network down"); },
    async () => { throw new Error("Fallback down"); },
  ));
  expect(h.patches).toEqual([{
    text: chatNoticeCopy.assistantErrorMessage, confidence: "low",
    notEnoughData: false, handoffSuggested: false, handoffReason: null,
  }]);
  expect(h.notices).toEqual([chatNoticeCopy.assistantUnavailable]);
  expect(h.operations).toEqual(["patch", "cancel"]);
});

test("aborted response does not trigger fallback or an error notice", async () => {
  const h = setup();
  let fallbackCalled = false;
  await runChatResponseFlow(h.options, transport(
    async () => { throw new DOMException("Aborted", "AbortError"); },
    async () => { fallbackCalled = true; throw new Error("Not expected"); },
  ));
  expect(fallbackCalled).toBe(false);
  expect(h.notices).toEqual([]);
  expect(h.patches).toEqual([]);
  expect(h.operations).toEqual(["cancel"]);
});
