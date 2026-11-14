/** Validated, shareable navigation state. No HR data or credentials in the URL. */
export const WORKFORCE_DEFAULT_MODE = "workforce-intelligence" as const;

export const WORKFORCE_MODES = [
  "workforce-intelligence",
  "workforce-management",
  "people-voice",
  "data-architecture",
] as const;

export type WorkforceMode = (typeof WORKFORCE_MODES)[number];

export function isWorkforceMode(value: unknown): value is WorkforceMode {
  return typeof value === "string" && WORKFORCE_MODES.some((mode) => mode === value);
}

/** Reject ambiguous duplicate parameters instead of guessing a section. */
export function modeFromSearch(search: string): WorkforceMode {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const values = params.getAll("mode");
  return values.length === 1 && isWorkforceMode(values[0])
    ? values[0]
    : WORKFORCE_DEFAULT_MODE;
}

/** Navigation intentionally drops unrelated URL parameters (including secrets). */
export function workforceModeHref(mode: WorkforceMode): string {
  return `/portfolio/workforce-intelligence?mode=${mode}`;
}
