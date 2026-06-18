import { projectConfig } from "./project-config";

const DEFAULT_SITE_URL = projectConfig.site.canonicalUrl;
const DEFAULT_LANGUAGE = "en";
const DEFAULT_OG_IMAGE_WIDTH = 1200;
const DEFAULT_OG_IMAGE_HEIGHT = 630;

export const publicRoutes = ["/", "/resume", "/chat", "/contact", "/disclaimer"];

export const siteNavigation = [
  { href: "/", label: "Home" },
  { href: "/resume", label: "Resume" },
  { href: "/chat", label: "Chat" },
  { href: "/contact", label: "Contact" },
] as const;

export const siteConfig = {
  footer: {
    disclaimerLabel: "Disclaimer",
    message: "Thanks for visiting",
  },
  language: DEFAULT_LANGUAGE,
  links: {
    ...projectConfig.links,
    website: projectConfig.site.canonicalUrl,
  },
  name: projectConfig.site.name,
  navigation: siteNavigation,
  ogImageAlt: projectConfig.seo.openGraph.imageAlt,
  ogImageHeight: DEFAULT_OG_IMAGE_HEIGHT,
  ogImagePath: projectConfig.seo.openGraph.imagePath,
  ogImageWidth: DEFAULT_OG_IMAGE_WIDTH,
  personName: projectConfig.owner.displayName,
  shortDescription: projectConfig.seo.shortDescription,
  title: projectConfig.seo.defaultTitle,
  titleTemplate: `%s | ${projectConfig.owner.displayName}`,
  description: projectConfig.seo.description,
  keywords: projectConfig.seo.keywords,
};

export function getSiteUrl() {
  const configuredUrl = process.env.SITE_URL ?? process.env.NEXT_PUBLIC_SITE_URL;
  const siteUrl = configuredUrl?.trim() || DEFAULT_SITE_URL;

  return siteUrl.replace(/\/+$/, "");
}

export function isPreviewDeployment() {
  return process.env.VERCEL_ENV === "preview";
}

export function getPersonJsonLd() {
  const siteUrl = getSiteUrl();
  const personJsonLd = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: siteConfig.personName,
    url: siteUrl,
    jobTitle: projectConfig.seo.jsonLd.jobTitle,
    sameAs: [siteConfig.links.github, siteConfig.links.linkedin],
    knowsAbout: projectConfig.seo.jsonLd.knowsAbout,
  };

  return JSON.stringify(personJsonLd).replace(/</g, "\\u003c");
}
