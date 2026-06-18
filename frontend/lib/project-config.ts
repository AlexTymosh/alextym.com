import rawProjectConfig from "../.generated/project.config.json";

export type ProjectConfig = typeof rawProjectConfig;
export type SeoPageId = keyof ProjectConfig["seo"]["pages"];
export type PublicLinkKey = keyof ProjectConfig["links"] & string;

export type PublicLink = {
  href: string;
  key: PublicLinkKey;
  label: string;
};

const linkLabels = {
  facebook: "Facebook",
  github: "GitHub",
  linkedin: "LinkedIn",
} satisfies Record<PublicLinkKey, string>;

const seoPageDefaults = {
  chat: {
    canonical: "/chat",
    title: "AI Profile Chat",
  },
  contact: {
    canonical: "/contact",
    title: "Contact",
  },
  disclaimer: {
    canonical: "/disclaimer",
    title: "Disclaimer",
  },
  resume: {
    canonical: "/resume",
    title: "Resume",
  },
} satisfies Record<SeoPageId, { canonical: string; title: string }>;

export const projectConfig = rawProjectConfig;
export const chatConfig = projectConfig.chat;
export const contactConfig = projectConfig.contact;
export const disclaimerConfig = projectConfig.disclaimer;
export const homeConfig = projectConfig.home;
export const ownerConfig = projectConfig.owner;
export const resumeConfig = projectConfig.resume;
export const siteIdentityConfig = projectConfig.site;
export const assistantConfig = {
  displayName: `${ownerConfig.possessiveName} digital assistant`,
  ownerReference: ownerConfig.shortName,
} as const;

export function getSeoPage(pageId: SeoPageId) {
  return {
    ...seoPageDefaults[pageId],
    description: projectConfig.seo.pages[pageId].description,
  };
}

export function getPublicLink(key: string): PublicLink | null {
  if (!isPublicLinkKey(key)) {
    return null;
  }

  return {
    href: projectConfig.links[key],
    key,
    label: linkLabels[key],
  };
}

export function getPublicLinks(keys: readonly string[]): PublicLink[] {
  return keys
    .map((key) => getPublicLink(key))
    .filter((link): link is PublicLink => Boolean(link));
}

function isPublicLinkKey(key: string): key is PublicLinkKey {
  return Object.prototype.hasOwnProperty.call(projectConfig.links, key);
}
