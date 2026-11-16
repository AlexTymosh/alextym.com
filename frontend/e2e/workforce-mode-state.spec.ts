import { expect, test } from "@playwright/test";
import { guideHref, INTERVIEW_GUIDES, readGuide } from "../../portfolio/workforce_intelligence/frontend/src/interview";
import {
  WORKFORCE_DEFAULT_MODE,
  WORKFORCE_LOCAL_PREVIEW_PATH,
  WORKFORCE_MODES,
  isWorkforceMode,
  modeFromSearch,
  screenFromLocation,
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

  test("restores only screens in the current mode from new and legacy links", () => {
    const url = new URL(workforceModeHref("people-voice", false, "voice-tracker"), "https://example.invalid");
    expect(screenFromLocation(modeFromSearch(url.search), url.search)).toBe("voice-tracker");
    expect(screenFromLocation("people-voice", "", "#voice-report")).toBe("voice-report");
    expect(screenFromLocation("people-voice", "", "#response-rota-001")).toBe("signals");
    expect(screenFromLocation("workforce-management", "?section=voice-tracker")).toBe("directory");
    expect(screenFromLocation("data-architecture", "?section=data-model&section=quality")).toBe("data-lineage");
    expect(workforceModeHref("people-voice", true, "signals")).toBe(`${WORKFORCE_LOCAL_PREVIEW_PATH}?mode=people-voice&section=signals`);
  });
});

test("guided URLs restore the exact step and reject an ambiguous or mismatched mode", () => {
  for (const name of ["quick", "extended"] as const) {
    INTERVIEW_GUIDES[name].steps.forEach((step, index) => {
      const url = new URL(guideHref(name, index), "https://example.invalid");
      expect(readGuide(url.search)).toEqual({ name, index, step });
    });
  }
  expect(readGuide("?mode=people-voice&scenario=quick&step=edit-fte")).toBeNull();
  expect(readGuide("?mode=workforce-management&scenario=quick&step=edit-fte&step=funnel")).toBeNull();
});
