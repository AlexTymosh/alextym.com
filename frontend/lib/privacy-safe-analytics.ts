type AnalyticsPage = "/" | "/resume" | "/chat" | "/contact";

type AnalyticsEventPayload =
  | {
      event: "page_view";
      page: AnalyticsPage;
    }
  | {
      event: "resume_download";
      source: "resume_page";
    };

const SAFE_ANALYTICS_PAGES = new Set<AnalyticsPage>([
  "/",
  "/resume",
  "/chat",
  "/contact",
]);

export function recordPageView(pathname: string | null | undefined): void {
  const page = normalizeAnalyticsPage(pathname);
  if (!page) {
    return;
  }

  void sendAnalyticsEvent({ event: "page_view", page });
}

export function recordResumeDownload(): void {
  void sendAnalyticsEvent({ event: "resume_download", source: "resume_page" });
}

function normalizeAnalyticsPage(
  pathname: string | null | undefined,
): AnalyticsPage | null {
  if (!pathname) {
    return null;
  }

  const pathWithoutQuery = pathname.split("?", 1)[0].split("#", 1)[0];
  const normalizedPath =
    pathWithoutQuery.length > 1
      ? pathWithoutQuery.replace(/\/+$/, "")
      : pathWithoutQuery;

  if (SAFE_ANALYTICS_PAGES.has(normalizedPath as AnalyticsPage)) {
    return normalizedPath as AnalyticsPage;
  }

  return null;
}

async function sendAnalyticsEvent(payload: AnalyticsEventPayload): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }

  try {
    await fetch("/api/analytics/events", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
      credentials: "omit",
      keepalive: true,
      referrerPolicy: "no-referrer",
    });
  } catch {
    // Analytics must never affect the user-facing website flow.
  }
}
