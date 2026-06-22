const STREAM_RENDER_TICK_MS = 100;
const STREAM_RENDER_BASE_CHARS = 6;
const STREAM_RENDER_MEDIUM_CHARS = 14;
const STREAM_RENDER_FAST_CHARS = 220;
const STREAM_RENDER_LARGE_BACKLOG = 720;
const STREAM_RENDER_MEDIUM_BACKLOG = 280;

export type StreamTextRenderer = {
  append: (text: string) => void;
  cancel: () => void;
  finish: () => Promise<void>;
  flush: () => void;
};

type StreamTextRendererOptions = {
  signal: AbortSignal;
  onUpdate: (text: string) => void;
};

export function createStreamTextRenderer({
  signal,
  onUpdate,
}: StreamTextRendererOptions): StreamTextRenderer {
  let pendingText = "";
  let visibleText = "";
  let isCancelled = false;
  let isFinishing = false;
  let timerId: number | null = null;
  let finishResolver: (() => void) | null = null;

  function append(text: string) {
    if (isCancelled || !text) {
      return;
    }

    pendingText += text;
    scheduleTick();
  }

  function scheduleTick() {
    if (isCancelled || timerId !== null) {
      return;
    }
    if (!pendingText) {
      resolveIfFinished();
      return;
    }

    timerId = window.setTimeout(runTick, STREAM_RENDER_TICK_MS);
  }

  function runTick() {
    timerId = null;
    if (isCancelled) {
      resolveIfFinished();
      return;
    }

    const batchSize = nextStreamRenderBatchSize(pendingText.length, isFinishing);
    const nextText = pendingText.slice(0, batchSize);
    pendingText = pendingText.slice(batchSize);
    visibleText += nextText;
    onUpdate(visibleText);

    if (pendingText) {
      scheduleTick();
      return;
    }

    resolveIfFinished();
  }

  function finish() {
    isFinishing = true;
    if (!pendingText) {
      return Promise.resolve();
    }

    scheduleTick();
    return new Promise<void>((resolve) => {
      finishResolver = resolve;
    });
  }

  function flush() {
    if (isCancelled || !pendingText) {
      return;
    }

    if (timerId !== null) {
      window.clearTimeout(timerId);
      timerId = null;
    }
    visibleText += pendingText;
    pendingText = "";
    onUpdate(visibleText);
    resolveIfFinished();
  }

  function cancel() {
    isCancelled = true;
    pendingText = "";
    if (timerId !== null) {
      window.clearTimeout(timerId);
      timerId = null;
    }
    resolveIfFinished();
  }

  function resolveIfFinished() {
    if (pendingText || !finishResolver) {
      return;
    }

    finishResolver();
    finishResolver = null;
  }

  signal.addEventListener("abort", cancel, { once: true });

  return {
    append,
    cancel,
    finish,
    flush,
  };
}

function nextStreamRenderBatchSize(
  pendingLength: number,
  isFinishing: boolean,
): number {
  if (pendingLength >= STREAM_RENDER_LARGE_BACKLOG) {
    return STREAM_RENDER_FAST_CHARS;
  }
  if (pendingLength >= STREAM_RENDER_MEDIUM_BACKLOG) {
    return STREAM_RENDER_MEDIUM_CHARS;
  }
  if (isFinishing && pendingLength > STREAM_RENDER_MEDIUM_CHARS) {
    return STREAM_RENDER_MEDIUM_CHARS;
  }

  return STREAM_RENDER_BASE_CHARS;
}
