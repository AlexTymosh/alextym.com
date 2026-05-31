import type { MetadataRoute } from "next";
import {
  getSiteUrl,
  isPreviewDeployment,
  publicRoutes,
} from "../lib/site-config";

export default function sitemap(): MetadataRoute.Sitemap {
  if (isPreviewDeployment()) {
    return [];
  }

  const siteUrl = getSiteUrl();

  return publicRoutes.map((route) => ({
    url: `${siteUrl}${route === "/" ? "" : route}`,
  }));
}
