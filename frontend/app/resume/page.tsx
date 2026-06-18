import type { Metadata } from "next";
import { getResumeData } from "../../content/resume";
import { getSeoPage } from "../../lib/project-config";
import { ResumeExplorer } from "./_components/ResumeExplorer";

const resumeSeo = getSeoPage("resume");

export const metadata: Metadata = {
  title: resumeSeo.title,
  description: resumeSeo.description,
  alternates: {
    canonical: resumeSeo.canonical,
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
