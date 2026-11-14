export function hasLabJsonContent(request: Request): boolean {
  return request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() ===
    "application/json";
}

export async function readLabJson(
  request: Request,
  limit: number,
): Promise<Record<string, unknown> | "too_large" | null> {
  if (Number(request.headers.get("content-length")) > limit) return "too_large";
  const reader = request.body?.getReader();
  if (!reader) return null;
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let raw = "";
  let size = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > limit) {
        void reader.cancel().catch(() => undefined);
        return "too_large";
      }
      raw += decoder.decode(chunk.value, { stream: true });
    }
    const value: unknown = JSON.parse(raw + decoder.decode());
    return value && typeof value === "object" && !Array.isArray(value)
      ? value as Record<string, unknown>
      : null;
  } catch {
    return null;
  }
}
