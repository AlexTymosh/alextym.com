import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteNavigation } from "../components/site-navigation";
import "./globals.css";
import "./chat-messages.css";

export const metadata: Metadata = {
  title: "alextym",
  description: "Personal AI portfolio website for Alex.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const themeScript =
    `(()=>{try{document.documentElement.dataset.theme=` +
    `localStorage.getItem("alextym-theme")||"dark"}catch(e){` +
    `document.documentElement.dataset.theme="dark"}})();`;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
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
