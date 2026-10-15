import type { Metadata } from "next";
import VorHub from "./VorHub";

export const metadata: Metadata = {
  title: "Fleet VOR Hub · Demo",
  description: "Synthetic fleet workflow and communications demonstration",
  robots: { index: false, follow: false },
};

export default function FleetVorDemoPage() {
  return <VorHub />;
}
