import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteNavigation } from "../components/site-navigation";
import "./globals.css";

export const metadata: Metadata = {
  title: "alextym",
  description: "Personal AI portfolio website for Alex.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const themeScript = `(()=>{try{document.documentElement.dataset.theme=localStorage.getItem("alextym-theme")||"dark"}catch(e){document.documentElement.dataset.theme="dark"}})();`;

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
            <span>{"{"}</span>
            <span>Thanks for visiting alextym.com</span>
            <span>{"}"}</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
