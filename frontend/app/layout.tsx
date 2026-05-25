import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "alextym",
  description: "Personal AI portfolio website for Alex.",
};

const navigation = [
  { href: "/", label: "Home" },
  { href: "/resume", label: "Resume" },
  { href: "/chat", label: "Chat" },
  { href: "/contact", label: "Contact" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-white text-zinc-950 antialiased dark:bg-zinc-950 dark:text-zinc-50">
        <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-6 py-6">
          <header className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-200 pb-4 dark:border-zinc-800">
            <Link href="/" className="text-lg font-semibold">
              alextym
            </Link>
            <nav aria-label="Main navigation" className="flex gap-4 text-sm">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-zinc-700 transition hover:text-zinc-950 dark:text-zinc-300 dark:hover:text-white"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </header>
          <main className="flex flex-1 flex-col py-10">{children}</main>
        </div>
      </body>
    </html>
  );
}
