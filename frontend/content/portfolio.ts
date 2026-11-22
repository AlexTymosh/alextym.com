type ProjectOverview = {
  focus: string;
  challenge: string;
  approach: string;
  highlights: readonly string[];
  preview: { src: string; alt: string; caption: string };
};

export const projectOverviews: Readonly<Partial<Record<string, ProjectOverview>>> = {
  fleet_hub: {
    focus: "One vehicle. Every issue. A shared conversation.",
    challenge: "A rapid concept for aligning a parent company and its subsidiary when their operational units differ: one tracks breakdown tickets, while the other manages vehicles and the events in each vehicle's lifecycle.",
    approach: "The prototype models a shared hub linking KEY2 ERP vehicle records with HoTH tickets and repair events. It gives internal departments and external partners one place to coordinate work, with conversations, decisions and next actions tied to the vehicle and its issues.",
    highlights: [
      "Connect vehicle records, defect tickets and repair events in one operational view.",
      "Keep partner communication and internal updates in a shared issue history.",
      "Explore repair workflows, operational controls and record reconciliation.",
      "Import your own vehicle records, process them through operational workflows and export fleet data to Excel.",
    ],
    preview: {
      src: "/images/portfolio/fleet-vor-hub-demo.png",
      alt: "Fleet Issue Hub with a synthetic vehicle, linked ticket, shared communication history and repair workflow.",
      caption: "Issue Hub · Example vehicle and repair workflow",
    },
  },
  workforce_intelligence: {
    focus: "From staff feedback to reviewed, measurable action.",
    challenge: "Staff feedback contains useful signals, but recurring themes, uneven participation and small samples make it difficult to decide what deserves attention. This concept connects text analysis with workforce and recruitment data.",
    approach: "AI groups written feedback into themes and proposes findings linked to supporting excerpts. Deterministic analytics calculate representation weights, effective sample sizes and review priorities. A human analyst reviews the evidence before findings are published and translated into management actions.",
    highlights: [
      "Compare weighted and unweighted feedback, with small-sample suppression.",
      "Review AI findings and evidence, then record decisions, recommended actions and outcomes.",
      "Explore an ERP-style workforce simulation: staffing records, recruitment funnels, conversion rates, forecasts and what-if scenarios.",
      "Import your own workforce dataset, validate and analyse it, then export Excel reports.",
    ],
    preview: {
      src: "/images/portfolio/workforce-intelligence-light.png",
      alt: "People Voice in light theme showing a reviewed synthetic staff-feedback finding, theme frequency and supporting evidence.",
      caption: "People Voice · Light theme · Seeded demonstration findings",
    },
  },
};
