import { expect, test } from "@playwright/test";

import { createChatRequestLifecycle } from "../lib/chat-request-lifecycle";

// These tests are intentionally independent of React, browser routing and timers.
test("assistant lease is current only while its request owns the slot", () => {
  const lifecycle = createChatRequestLifecycle();
  expect(lifecycle.hasActiveAssistant()).toBe(false);
  const request = lifecycle.beginAssistantRequest();
  expect(lifecycle.hasActiveAssistant()).toBe(true);
  expect(request.isCurrent()).toBe(true);
  expect(request.signal.aborted).toBe(false);
  request.finish();
  expect(lifecycle.hasActiveAssistant()).toBe(false);
  expect(request.isCurrent()).toBe(false);
});

test("reset invalidates a request, aborts it and clears the slot", () => {
  const lifecycle = createChatRequestLifecycle();
  const request = lifecycle.beginAssistantRequest();
  lifecycle.invalidate();
  expect(request.signal.aborted).toBe(true);
  expect(request.isCurrent()).toBe(false);
  expect(lifecycle.hasActiveAssistant()).toBe(false);
});

test("stale completion cannot release a newer request", () => {
  const lifecycle = createChatRequestLifecycle();
  const first = lifecycle.beginAssistantRequest();
  const second = lifecycle.beginAssistantRequest();
  expect(first.signal.aborted).toBe(true);
  expect(first.isCurrent()).toBe(false);
  first.finish();
  expect(second.isCurrent()).toBe(true);
  expect(lifecycle.hasActiveAssistant()).toBe(true);
  second.finish();
  expect(lifecycle.hasActiveAssistant()).toBe(false);
});

test("a new request after reset does not revive the old lease", () => {
  const lifecycle = createChatRequestLifecycle();
  const old = lifecycle.beginAssistantRequest();
  lifecycle.invalidate();
  const current = lifecycle.beginAssistantRequest();
  old.finish();
  expect(old.isCurrent()).toBe(false);
  expect(current.isCurrent()).toBe(true);
});

test("handoff session callbacks become invalid after reset", () => {
  const lifecycle = createChatRequestLifecycle();
  const oldSession = lifecycle.captureSession();
  expect(oldSession()).toBe(true);
  lifecycle.invalidate();
  expect(oldSession()).toBe(false);
  const currentSession = lifecycle.captureSession();
  expect(currentSession()).toBe(true);
});

test("finishing one assistant request does not invalidate its handoff session", () => {
  const lifecycle = createChatRequestLifecycle();
  const session = lifecycle.captureSession();
  lifecycle.beginAssistantRequest().finish();
  expect(session()).toBe(true);
});

test("repeated invalidation keeps all earlier leases obsolete", () => {
  const lifecycle = createChatRequestLifecycle();
  const first = lifecycle.captureSession();
  lifecycle.invalidate();
  const second = lifecycle.captureSession();
  lifecycle.invalidate();
  expect(first()).toBe(false);
  expect(second()).toBe(false);
  expect(lifecycle.captureSession()()).toBe(true);
});
