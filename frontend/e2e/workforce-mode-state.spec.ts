import { expect, test } from "@playwright/test";
import {
  WORKFORCE_DEFAULT_MODE,
  WORKFORCE_LOCAL_PREVIEW_PATH,
  WORKFORCE_MODES,
  isWorkforceMode,
  modeFromSearch,
  workforceModeHref,
} from "../../portfolio/workforce_intelligence/frontend/src/mode-state";

test.describe("Workforce SPA navigation state (no authentication bypass)", () => {
  test("defines four distinct project-owned modes with Intelligence as default", () => {
    expect(WORKFORCE_MODES).toHaveLength(4);
    expect(new Set(WORKFORCE_MODES).size).toBe(4);
    expect(WORKFORCE_DEFAULT_MODE).toBe("workforce-intelligence");
  });

  for (const mode of WORKFORCE_MODES) {
    test(`round-trips a deep link for ${mode}`, () => {
      expect(isWorkforceMode(mode)).toBe(true);
      const href = workforceModeHref(mode);
      expect(href.startsWith("/portfolio/workforce-intelligence?mode=")).toBe(true);
      expect(modeFromSearch(new URL(href, "https://example.invalid").search)).toBe(mode);
    });
  }

  test("keeps preview-mode links on the isolated local route", () => {
    for (const mode of WORKFORCE_MODES) {
      const href = workforceModeHref(mode, true);
      expect(href).toBe(`${WORKFORCE_LOCAL_PREVIEW_PATH}?mode=${mode}`);
      expect(modeFromSearch(new URL(href, "https://example.invalid").search)).toBe(mode);
    }
  });

  test("defaults empty, unknown, duplicate and case-changed mode values", () => {
    for (const search of ["", "?mode=", "?mode=unknown", "?mode=PEOPLE-VOICE",
      "?mode=people-voice&mode=workforce-management", "?mode=%2F%2Fmalicious"]) {
      expect(modeFromSearch(search)).toBe(WORKFORCE_DEFAULT_MODE);
    }
    expect(isWorkforceMode("people-voice" + "/override")).toBe(false);
    expect(isWorkforceMode(null)).toBe(false);
  });

  test("ignores extra query parameters and builds a canonical clean destination", () => {
    expect(modeFromSearch("?mode=people-voice&untrusted=sensitive")).toBe("people-voice");
    expect(workforceModeHref("people-voice")).toBe("/portfolio/workforce-intelligence?mode=people-voice");
  });
});
