"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

const storageKey = "alextym-theme";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(storageKey, theme);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const storedTheme = localStorage.getItem(storageKey);
    const initialTheme: Theme = storedTheme === "light" ? "light" : "dark";
    setTheme(initialTheme);
    document.documentElement.dataset.theme = initialTheme;
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
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
