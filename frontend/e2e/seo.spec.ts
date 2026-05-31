import { expect, test } from "@playwright/test";

const siteUrl = "https://alextym.com";

const pageMetadataCases = [
  {
    path: "/",
    title: "Alex Tymoshenko | Software Developer & Automation Engineer",
    description: /Python, FastAPI, API integrations/,
  },
  {
    path: "/resume",
    title: "Resume | Alex Tymoshenko",
    description: /Resume of Alex Tymoshenko/,
  },
  {
    path: "/chat",
    title: "AI Profile Chat | Alex Tymoshenko",
    description: /AI profile assistant/,
  },
  {
    path: "/contact",
    title: "Contact | Alex Tymoshenko",
    description: /Contact Alex Tymoshenko/,
  },
];

test.describe("SEO metadata", () => {
  for (const metadataCase of pageMetadataCases) {
    test(`${metadataCase.path} exposes expected title and description`, async ({
      page,
    }) => {
      await page.goto(metadataCase.path);

      await expect(page).toHaveTitle(metadataCase.title);
      await expect(page.locator('meta[name="description"]')).toHaveAttribute(
        "content",
        metadataCase.description,
      );
    });
  }

  test("home exposes social preview and structured data", async ({ page }) => {
    await page.goto("/");

    await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
      "content",
      "Alex Tymoshenko | Software Developer & Automation Engineer",
    );
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
      "content",
      `${siteUrl}/og-image.png`,
    );
    await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute(
      "content",
      "summary_large_image",
    );
    const canonicalHref = await page
      .locator('link[rel="canonical"]')
      .getAttribute("href");

    expect(canonicalHref?.replace(/\/$/, "")).toBe(
      siteUrl.replace(/\/$/, ""),
    );
    const jsonLd = await page
      .locator('script[type="application/ld+json"]')
      .first()
      .evaluate((element) => element.textContent ?? "");

    const structuredData = JSON.parse(jsonLd) as {
      "@type": string;
      name: string;
    };

    expect(structuredData["@type"]).toBe("Person");
    expect(structuredData.name).toBe("Alex Tymoshenko");
  });

  test("robots.txt allows public pages and blocks api routes", async ({ page }) => {
    await page.goto("/robots.txt");

    await expect(page.locator("body")).toContainText("User-Agent: *");
    await expect(page.locator("body")).toContainText("Allow: /");
    await expect(page.locator("body")).toContainText("Disallow: /api/");
    await expect(page.locator("body")).toContainText(
      `Sitemap: ${siteUrl}/sitemap.xml`,
    );
  });

  test("sitemap.xml lists canonical public pages", async ({ page }) => {
    await page.goto("/sitemap.xml");

    await expect(page.locator("body")).toContainText(`<loc>${siteUrl}</loc>`);
    await expect(page.locator("body")).toContainText(
      `<loc>${siteUrl}/resume</loc>`,
    );
    await expect(page.locator("body")).toContainText(
      `<loc>${siteUrl}/chat</loc>`,
    );
    await expect(page.locator("body")).toContainText(
      `<loc>${siteUrl}/contact</loc>`,
    );
  });
});
