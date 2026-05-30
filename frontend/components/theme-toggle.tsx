"use client";

import { useSyncExternalStore } from "react";

type Theme = "dark" | "light";

const storageKey = "alextym-theme";
const themeChangeEvent = "alextym-theme-change";

function normalizeTheme(value: string | null | undefined): Theme | null {
  if (value === "light" || value === "dark") {
    return value;
  }

  return null;
}

function readStoredTheme(): Theme | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return normalizeTheme(window.localStorage.getItem(storageKey));
  } catch {
    return null;
  }
}

function readDocumentTheme(): Theme | null {
  if (typeof document === "undefined") {
    return null;
  }

  return normalizeTheme(document.documentElement.dataset.theme);
}

function readTheme(): Theme {
  return readStoredTheme() ?? readDocumentTheme() ?? "dark";
}

function subscribeToThemeChanges(callback: () => void) {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  window.addEventListener("storage", callback);
  window.addEventListener(themeChangeEvent, callback);

  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(themeChangeEvent, callback);
  };
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;

  try {
    window.localStorage.setItem(storageKey, theme);
  } catch {
    // The DOM theme still changes if storage is unavailable.
  }

  window.dispatchEvent(new Event(themeChangeEvent));
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    subscribeToThemeChanges,
    readTheme,
    () => "dark",
  );

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";

    applyTheme(nextTheme);
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      <span className="theme-toggle__icon" aria-hidden="true">
        {theme === "dark" ? (
          <svg viewBox="0 0 24 24" role="img">
            <path d="M12 4.5V2m0 20v-2.5M4.5 12H2m20 0h-2.5m-2.32-6.68 1.77-1.77M5.05 18.95l1.77-1.77m0-10.36L5.05 5.05m13.9 13.9-1.77-1.77" />
            <circle cx="12" cy="12" r="4.25" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" role="img">
            <path d="M20.2 14.4A7.8 7.8 0 0 1 9.6 3.8 8.1 8.1 0 1 0 20.2 14.4Z" />
          </svg>
        )}
      </span>
    </button>
  );
}
