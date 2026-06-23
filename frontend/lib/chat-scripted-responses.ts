import { SCRIPTED_RESPONSE_DELAY_MS } from "../content/chat";

export async function waitForScriptedResponse(
  signal: AbortSignal,
): Promise<void> {
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

export function chooseScriptedResponse(responses: readonly string[]): string {
  return (
    responses[Math.floor(Math.random() * responses.length)] ||
    responses[0] ||
    ""
  );
}
