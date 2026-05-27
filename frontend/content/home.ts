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

export const profileCard = {
  name: "Alex Tymoshenko",
  imageSrc: "/images/profile/alex.webp",
  imageAlt: "",
  summary:
    "I build practical automation tools that connect APIs, Excel, ERP systems, reports, and dashboards into smoother business workflows.",
} satisfies ProfileCard;

export const assistantCard = {
  eyebrow: "AI Profile Chat",
  title: "Quick questions",
  description: "Save time by asking about my projects, CV, and automation experience.",
  cta: "Ask my AI assistant",
  href: "/chat",
} satisfies AssistantCard;

export const featuredProject: FeaturedProject = {
  previewHeading: "Latest Projects in Progress",
  title: "yourname.com",
  description: [
    "Build your own AI portfolio website.",
    "I open-sourced this site as a reusable MIT-licensed template. Follow the setup guide, replace the public CV and project content, and make it your own.",
  ],
  cta: "Get the setup guide",
  href: "https://github.com/AlexTymosh/alextym.com",
  previewItems: [
    {
      title: "FastAPI SaaS Template",
      detail: "GDPR-aware modular backend with tenant access, audit, rate limiting, and API contracts.",
      href: "https://github.com/AlexTymosh/fastapi-saas-template",
      slot: "top-left",
    },
    {
      title: "Job Application AI Assistant",
      detail: "CV tailoring, ATS-style checks, and evidence-based application support.",
      href: "https://github.com/AlexTymosh/job-application-assistant",
      slot: "top-right",
    },
    {
      title: "alextym.com",
      detail: "RAG-based AI portfolio with public CV, chat, contact flow, and reusable setup path.",
      href: "https://github.com/AlexTymosh/alextym.com",
      slot: "bottom-right",
    },
  ],
};

export const featuredAutomationDemo = {
  eyebrow: "Unusual Automation",
  title: "Excel API Magic",
  description: "Making Excel work like a modern business system.",
  youtubeVideoId: "uAvHcnk1ym8",
  youtubeTitle: "Excel API Integration demo",
  cta: "Open on YouTube",
} satisfies FeaturedAutomationDemo;

export const buildFocus = {
  eyebrow: "Current Engineering Focus",
  title: "SaaS backend systems with GDPR-aware architecture",
  description:
    "Most of my current effort goes into a FastAPI SaaS backend template: a modular monolith for small and medium SaaS products with tenant/platform access control, Keycloak OIDC/JWT, audit and outbox foundations, Redis-backed rate limiting, structured errors, testing, and observability.",
} satisfies BuildFocus;

export const projectStack = [
  "Python 3.12",
  "FastAPI",
  "Pydantic v2",
  "SQLAlchemy",
  "Alembic",
  "PostgreSQL",
  "Redis",
  "Keycloak/OIDC",
  "Dramatiq",
  "Docker Compose",
  "uv",
  "Ruff",
  "Pytest",
  "OpenTelemetry",
] satisfies ProjectStackItem[];
