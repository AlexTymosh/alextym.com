import { expect, test } from "@playwright/test";

test("renders the resume and switches detail level", async ({ page }) => {
  await page.goto("/resume");

  await expect(
    page.getByRole("heading", { name: "Alex Tymoshenko" }),
  ).toBeVisible();
  await expect(page.getByText("Automation Engineer focused")).toBeVisible();
  await expect(
    page.getByText("Built an Odoo ERP-integrated API"),
  ).toBeVisible();

  await page.getByRole("button", { name: "Detailed" }).click();

  await expect(
    page.getByText("Architected and deployed an internal API"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /detailed CV/i }),
  ).toHaveAttribute("href", "/resume/alex-tymoshenko-cv-detailed.pdf");
});

test("shows experience and education by default", async ({ page }) => {
  await page.goto("/resume");

  const timeline = page.getByLabel("Resume timeline");
  const experienceButton = page.getByRole("button", { name: "Experience" });
  const educationButton = page.getByRole("button", { name: "Education" });
  const trainingButton = page.getByRole("button", { name: "Training" });

  await expect(experienceButton).toHaveAttribute("aria-pressed", "true");
  await expect(educationButton).toHaveAttribute("aria-pressed", "true");
  await expect(trainingButton).toHaveAttribute("aria-pressed", "false");

  await expect(timeline.getByText("Work Experience")).toBeVisible();
  await expect(timeline.getByText("Education")).toBeVisible();
  await expect(page.getByText("Hydrosphere UK Ltd")).toBeVisible();
  await expect(
    page.getByText("Master's Degree in Finance, Banking and Insurance"),
  ).toBeVisible();
  await expect(
    page.getByText("Intermediate Backend Development with FastAPI"),
  ).toBeHidden();
});

test("keeps resume section filters independent", async ({ page }) => {
  await page.goto("/resume");

  const timeline = page.getByLabel("Resume timeline");
  const experienceButton = page.getByRole("button", { name: "Experience" });
  const educationButton = page.getByRole("button", { name: "Education" });
  const trainingButton = page.getByRole("button", { name: "Training" });

  await trainingButton.click();

  await expect(trainingButton).toHaveAttribute("aria-pressed", "true");
  await expect(timeline.getByText("Training")).toBeVisible();
  await expect(
    page.getByText("Intermediate Backend Development with FastAPI"),
  ).toBeVisible();

  await educationButton.click();

  await expect(educationButton).toHaveAttribute("aria-pressed", "false");
  await expect(timeline.getByText("Education")).toBeHidden();
  await expect(
    page.getByText("Master's Degree in Finance, Banking and Insurance"),
  ).toBeHidden();
  await expect(page.getByText("Hydrosphere UK Ltd")).toBeVisible();
  await expect(
    page.getByText("Intermediate Backend Development with FastAPI"),
  ).toBeVisible();

  await experienceButton.click();

  await expect(experienceButton).toHaveAttribute("aria-pressed", "false");
  await expect(timeline.getByText("Work Experience")).toBeHidden();
  await expect(page.getByText("Hydrosphere UK Ltd")).toBeHidden();
  await expect(timeline.getByText("Training")).toBeVisible();
});

test("splits concise and detailed education entries", async ({ page }) => {
  await page.goto("/resume");

  const timeline = page.getByLabel("Resume timeline");

  await expect(timeline.getByText("Education")).toBeVisible();
  await expect(
    page.getByText("Master's Degree in Finance, Banking and Insurance"),
  ).toBeVisible();
  await expect(
    page.getByText("Bachelor's Degree in Finance and Credit"),
  ).toBeHidden();
  await expect(page.getByText("Graduated with honours.")).toBeVisible();

  await page.getByRole("button", { name: "Detailed" }).click();

  await expect(
    page.getByText("Master's Degree in Finance, Banking and Insurance"),
  ).toBeVisible();
  await expect(
    page.getByText("Bachelor's Degree in Finance and Credit"),
  ).toBeVisible();
  await expect(
    page.getByText("Overall average score: 91.4/100."),
  ).toBeVisible();
});

test("shows an empty state when every section is disabled", async ({ page }) => {
  await page.goto("/resume");

  await page.getByRole("button", { name: "Experience" }).click();
  await page.getByRole("button", { name: "Education" }).click();

  await expect(page.getByText("Hydrosphere UK Ltd")).toBeHidden();
  await expect(
    page.getByText(/Select at least one section/i),
  ).toBeVisible();
});

test("sorts visible entries by section before date", async ({ page }) => {
  await page.goto("/resume");

  await page.getByRole("button", { name: "Detailed" }).click();
  await page.getByRole("button", { name: "Training" }).click();

  const titles = await page.locator("article h2").allTextContents();

  expect(titles.slice(0, 4)).toEqual([
    "Systems Integration & Automation Engineer",
    "Founder and Managing Director",
    "Master's Degree in Finance, Banking and Insurance",
    "Bachelor's Degree in Finance and Credit",
  ]);

  expect(
    titles.indexOf("Intermediate Backend Development with FastAPI"),
  ).toBeGreaterThan(
    titles.indexOf("Bachelor's Degree in Finance and Credit"),
  );
});
