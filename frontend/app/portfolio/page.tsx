import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = {
  title: "Portfolio Lab projects",
  robots: { index: false, follow: false },
};

/** Catalogue is private until shared per-project access checks are available. */
export default function PortfolioCataloguePage() {
  notFound();
}
