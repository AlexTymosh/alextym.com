import { getResumeData } from "../../content/resume";
import { ResumeExplorer } from "./_components/ResumeExplorer";

export default function ResumePage() {
  const resumeData = getResumeData();

  return (
    <section className="page-panel resume-panel">
      <ResumeExplorer resumeData={resumeData} />
    </section>
  );
}
