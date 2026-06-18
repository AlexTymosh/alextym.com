import { expect, test } from "@playwright/test";
import { getSeoPage, projectConfig } from "../lib/project-config";
import { publicRoutes, siteConfig } from "../lib/site-config";

const siteUrl = projectConfig.site.canonicalUrl;

const pageMetadataCases = [
  {
    path: "/",
    title: projectConfig.seo.defaultTitle,
    description: projectConfig.seo.description,
  },
  {
    path: "/resume",
    title: formatPageTitle(getSeoPage("resume").title),
    description: getSeoPage("resume").description,
  },
  {
    path: "/chat",
    title: formatPageTitle(getSeoPage("chat").title),
    description: getSeoPage("chat").description,
  },
  {
    path: "/contact",
    title: formatPageTitle(getSeoPage("contact").title),
    description: getSeoPage("contact").description,
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
      projectConfig.seo.defaultTitle,
    );
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
      "content",
      absoluteSiteUrl(projectConfig.seo.openGraph.imagePath),
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
    expect(structuredData.name).toBe(projectConfig.owner.displayName);
  });

  test("robots.txt allows public pages and blocks api routes", async ({ page }) => {
    await page.goto("/robots.txt");

    await expect(page.locator("body")).toContainText("User-Agent: *");
    await expect(page.locator("body")).toContainText("Allow: /");
    await expect(page.locator("body")).toContainText("Disallow: /api/");
    await expect(page.locator("body")).toContainText(`Sitemap: ${siteUrl}/sitemap.xml`);
  });

  test("sitemap.xml lists canonical public pages", async ({ page }) => {
    await page.goto("/sitemap.xml");

    for (const route of publicRoutes) {
      await expect(page.locator("body")).toContainText(
        `<loc>${absoluteSiteUrl(route)}</loc>`,
      );
    }
  });
});

function formatPageTitle(title: string): string {
  return siteConfig.titleTemplate.replace("%s", title);
}

function absoluteSiteUrl(path: string): string {
  return `${siteUrl}${path === "/" ? "" : path}`;
}
