const DEFAULT_SITE_URL = "https://alextym.com";

export const publicRoutes = [
  "/",
  "/resume",
  "/chat",
  "/contact",
  "/disclaimer",
] as const;

export const siteConfig = {
  name: "alextym.com",
  personName: "Alex Tymoshenko",
  title: "Alex Tymoshenko | Software Developer & Automation Engineer",
  description:
    "Software developer focused on Python, FastAPI, API integrations, " +
    "business process automation, ERP/CRM workflows, and RAG-based AI " +
    "portfolio systems.",
  shortDescription:
    "Python, FastAPI, API integrations, business process automation, " +
    "ERP/CRM workflows, and RAG-based AI portfolio systems.",
  ogImagePath: "/og-image.png",
  links: {
    github: "https://github.com/AlexTymosh",
    linkedin: "https://www.linkedin.com/in/alex-tim-tech/",
  },
  keywords: [
    "Alex Tymoshenko",
    "Software Developer",
    "Python Developer",
    "FastAPI",
    "Automation Engineer",
    "API Integration",
    "Business Process Automation",
    "ERP Automation",
    "RAG",
    "AI Portfolio",
    "Basingstoke",
    "UK",
  ],
} as const;

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
    jobTitle: "Software Developer",
    sameAs: [siteConfig.links.github, siteConfig.links.linkedin],
    knowsAbout: [
      "Python",
      "FastAPI",
      "API integrations",
      "Business process automation",
      "ERP/CRM automation",
      "RAG systems",
    ],
  };

  return JSON.stringify(personJsonLd).replace(/</g, "\\u003c");
}
