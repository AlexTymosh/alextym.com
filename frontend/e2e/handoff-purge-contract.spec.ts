import { expect, test } from "@playwright/test";

import { purgeEscalationSession, submitEscalationClose } from "../lib/escalation-api";

test("purge uses DELETE and accepts only an acknowledged 204", async () => {
  const originalFetch = globalThis.fetch;
  const calls: { url: string; method?: string }[] = [];
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), method: init?.method });
    return new Response(null, { status: 204 });
  };
  try {
    await purgeEscalationSession("hnd_token/value");
    expect(calls).toEqual([{
      url: "/api/escalations/hnd_token%2Fvalue",
      method: "DELETE",
    }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("purge rejects HTTP errors rather than claiming deletion", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(null, { status: 503 });
  try {
    await expect(purgeEscalationSession("hnd_test")).rejects.toThrow("not acknowledged");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("manual close remains POST /close and is not changed to DELETE", async () => {
  const originalFetch = globalThis.fetch;
  const methods: string[] = [];
  globalThis.fetch = async (input, init) => {
    methods.push(`${init?.method} ${String(input)}`);
    return new Response(JSON.stringify({ status: "ok", state: "closed" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    expect(await submitEscalationClose("hnd_test")).toEqual({status: "ok", state: "closed"});
    expect(methods).toEqual(["POST /api/escalations/hnd_test/close"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
