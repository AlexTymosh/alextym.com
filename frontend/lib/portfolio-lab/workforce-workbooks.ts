export const XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
export const MAX_WORKBOOK_BYTES = 1024 * 1024;

export async function readWorkbookBytes(source: Request | Response): Promise<ArrayBuffer | "too_large" | null> {
  if (Number(source.headers.get("content-length")) > MAX_WORKBOOK_BYTES) return "too_large";
  const reader = source.body?.getReader();
  if (!reader) return null;
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      total += chunk.value.byteLength;
      if (total > MAX_WORKBOOK_BYTES) {
        void reader.cancel().catch(() => undefined);
        return "too_large";
      }
      chunks.push(chunk.value);
    }
    if (total === 0) return null;
    const buffer = new ArrayBuffer(total);
    const combined = new Uint8Array(buffer);
    let offset = 0;
    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return buffer;
  } catch {
    return null;
  } finally {
    reader.releaseLock();
  }
}

export function hasWorkbookContent(source: Request | Response): boolean {
  return source.headers.get("content-type")?.split(";")[0].trim().toLowerCase() === XLSX_CONTENT_TYPE;
}
