import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { PrivacySafeAnalytics } from "../components/privacy-safe-analytics";
import { SiteNavigation } from "../components/site-navigation";
import {
  getPersonJsonLd,
  getSiteUrl,
  isPreviewDeployment,
  siteConfig,
} from "../lib/site-config";
import "./globals.css";
import "./chat-messages.css";
import "./theme-overrides.css";
import "./footer-disclaimer.css";

const siteUrl = getSiteUrl();
const isPreview = isPreviewDeployment();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteConfig.title,
    template: siteConfig.titleTemplate,
  },
  description: siteConfig.description,
  applicationName: siteConfig.name,
  authors: [{ name: siteConfig.personName }],
  creator: siteConfig.personName,
  publisher: siteConfig.personName,
  keywords: [...siteConfig.keywords],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    siteName: siteConfig.name,
    title: siteConfig.title,
    description: siteConfig.shortDescription,
    images: [
      {
        url: siteConfig.ogImagePath,
        width: siteConfig.ogImageWidth,
        height: siteConfig.ogImageHeight,
        alt: siteConfig.ogImageAlt,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteConfig.title,
    description: siteConfig.shortDescription,
    images: [siteConfig.ogImagePath],
  },
  robots: {
    index: !isPreview,
    follow: !isPreview,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const themeScript = `
(() => {
  try {
    const storedTheme = localStorage.getItem("alextym-theme");
    const theme = storedTheme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
  } catch {
    document.documentElement.dataset.theme = "dark";
  }
})();`;

  return (
    <html lang={siteConfig.language} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: getPersonJsonLd() }}
        />
      </head>
      <body>
        <PrivacySafeAnalytics />
        <div className="app-shell">
          <SiteNavigation />
          <main className="site-main">{children}</main>
          <footer className="site-footer site-footer--with-disclaimer">
            <div className="site-footer__visit">
              <span className="site-footer__bracket">{"{"}</span>
              <span className="site-footer__message">{siteConfig.footer.message}</span>
              <span className="site-footer__domain">{siteConfig.name}</span>
              <span className="site-footer__bracket">{"}"}</span>
            </div>
            <Link className="site-footer__disclaimer" href="/disclaimer">
              {siteConfig.footer.disclaimerLabel}
            </Link>
          </footer>
        </div>
      </body>
    </html>
  );
}
