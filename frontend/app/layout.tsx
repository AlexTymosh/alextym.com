import type { Metadata } from "next";
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

const siteUrl = getSiteUrl();
const isPreview = isPreviewDeployment();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteConfig.title,
    template: "%s | Alex Tymoshenko",
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
        width: 1200,
        height: 630,
        alt: "Alex Tymoshenko software developer portfolio",
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
    <html lang="en" suppressHydrationWarning>
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
          <footer className="site-footer">
            <span className="site-footer__bracket">{"{"}</span>
            <span className="site-footer__message">Thanks for visiting</span>
            <span className="site-footer__domain">alextym.com</span>
            <span className="site-footer__bracket">{"}"}</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
