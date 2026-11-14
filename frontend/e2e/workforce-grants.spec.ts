import { expect, test } from "@playwright/test";
import cases from "../../docs/contracts/workforce-grant-cases.json";
import { adminGrantAllows } from "../lib/portfolio-lab/project-grants";

test.describe("Workforce shared grant contract", () => {
  for (const entry of cases) {
    test(entry.name, () => {
      expect(adminGrantAllows(entry.uid, entry.project_id, entry.record, entry.now_ms))
        .toBe(entry.want);
    });
  }
});
