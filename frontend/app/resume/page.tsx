import { resumeEntries } from "../../content/resume";
import { ResumeTimeline } from "./_components/ResumeTimeline";

export default function ResumePage() {
  return (
    <section className="page-panel resume-panel">
      <div className="resume-panel__header">
        <p className="eyebrow">Resume</p>
        <h1>Alex Tymoshenko</h1>
        <p>
          Public CV summary with a downloadable PDF version. The PDF file will be added later without
          phone number or email.
        </p>
      </div>

      <a className="primary-link resume-download" href="/resume/alex-tymoshenko-cv.pdf" download>
        Download CV
      </a>

      <ResumeTimeline entries={resumeEntries} />
    </section>
  );
}
