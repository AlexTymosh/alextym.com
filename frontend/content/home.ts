import { homeConfig } from "../lib/project-config";

export type ProjectStackItem = string;

export type ProfileCard = {
  name: string;
  imageSrc: string;
  imageAlt: string;
  summary: string;
};

export type AssistantCard = {
  eyebrow: string;
  title: string;
  description: string;
  cta: string;
  href: string;
};

export type ConnectCard = {
  eyebrow: string;
  linkVisibility: Record<string, boolean>;
};

export type FeaturedProjectPreviewItem = {
  title: string;
  detail: string;
  href: string;
  slot: "top-left" | "top-right" | "bottom-right";
  imageSrc?: string;
  imageAlt?: string;
};

export type FeaturedProject = {
  previewHeading: string;
  title: string;
  description: string[];
  cta: string;
  href: string;
  previewItems: FeaturedProjectPreviewItem[];
};

export type FeaturedAutomationDemo = {
  eyebrow: string;
  title: string;
  description: string;
  youtubeVideoId: string;
  youtubeTitle: string;
  cta: string;
};

export type BuildFocus = {
  eyebrow: string;
  title: string;
  description: string;
};

export const profileCard = homeConfig.profileCard as ProfileCard;
export const assistantCard = homeConfig.assistantCard as AssistantCard;
export const connectCard = homeConfig.connectCard as ConnectCard;
export const featuredProject =
  homeConfig.featuredProject as FeaturedProject;
export const featuredAutomationDemo =
  homeConfig.featuredAutomationDemo as FeaturedAutomationDemo;
export const buildFocus = homeConfig.buildFocus as BuildFocus;
export const projectStack = homeConfig.projectStack as ProjectStackItem[];
export const projectStackTitle = homeConfig.projectStackTitle;

export function getVisibleConnectLinkKeys(): string[] {
  return Object.entries(connectCard.linkVisibility)
    .filter(([, isVisible]) => isVisible)
    .map(([key]) => key);
}
