import type { Metadata } from "next";
import { getResumeData } from "../../content/resume";
import { ResumeExplorer } from "./_components/ResumeExplorer";

export const metadata: Metadata = {
  title: "Resume",
  description:
    "Resume of Alex Tymoshenko: software developer focused on Python, " +
    "FastAPI, automation, API integrations, ERP/CRM workflows, and " +
    "business systems.",
  alternates: {
    canonical: "/resume",
  },
};

export default function ResumePage() {
  const resumeData = getResumeData();

  return (
    <section className="page-panel resume-panel">
      <ResumeExplorer resumeData={resumeData} />
    </section>
  );
}
