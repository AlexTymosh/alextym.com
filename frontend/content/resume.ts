export type ResumeEntry = {
  id: string;
  /**
   * Public resume date.
   * Prefer YYYY-MM when the month is safe to publish.
   * Use YYYY only when the exact month is unknown or intentionally omitted.
   */
  startDate: string;
  /**
   * Public resume date.
   * Use null for a current role, rendered as "Present".
   */
  endDate: string | null;
  title: string;
  company?: string;
  location?: string;
  bullets: string[];
};

export const resumeEntries = [
  {
    id: "hydrosphere-systems-integration-2024-2026",
    startDate: "2024-09",
    endDate: "2026-04",
    title: "Systems Integration & Automation Engineer",
    company: "Hydrosphere UK Ltd",
    location: "United Kingdom",
    bullets: [
      "• Architected and deployed a full-featured ERP-integrated API, reducing one specialist’s manual workload by 68.0%",
      "• Designed and automated product matrix generation for ~800 plates, creating 7,000+ variants and controlling 21,000+ pricing points.",
      "• Built and maintained 50+ operational and IoT dashboards, analysing data to support decision-making for internal teams and external partners.",
    ],
  },
  {
    id: "professional-development-2022-2024",
    startDate: "2022-09",
    endDate: "2024-08",
    title: "Career Break & Professional Development",
    company: "Rebuilt career direction in the UK around software development",
    location: "United Kingdom",
    bullets: [
      "• English language development: structured English language courses from A1 to B1/B2 (Intermediate+)",
      "• Technical upskilling: completed IBM data courses and backend upskilling in Python, AI & Development, databases, data analysis, data visualisation, and FastAPI",
    ],
  },
  {
    id: "dobra-praca-managing-director-2015-2022",
    startDate: "2015-01",
    endDate: "2022-02",
    title: "Managing Director",
    company: "Dobra Praca LTD",
    location: "Ukraine",
    bullets: [
      "• Designed and executed migration from 30+ Excel spreadsheets into a unified relational database architecture (100,000+ records), improving data integrity and eliminating manual processing errors",
      "• Implemented automation across CRM-style workflows, IP telephony, website bots, Excel/VBA tools, reporting and document-processing tasks.",
      "• Led the company to win a regional industry award, achieving 1st place in its sector in 2018 (regional population: 1.7M)",
    ],
  },
] satisfies ResumeEntry[];
