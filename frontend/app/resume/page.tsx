const resumeHighlights = [
  "AI automation and RAG-focused portfolio work",
  "FastAPI backend and Next.js frontend delivery",
  "Business process background with software engineering execution",
];

export default function ResumePage() {
  return (
    <section className="page-panel resume-panel">
      <div>
        <p className="eyebrow">Resume</p>
        <h1>Alex Tymoshenko</h1>
        <p>
          Short public CV download. The PDF file will be added later without phone number or email.
        </p>
      </div>

      <a className="primary-link" href="/resume/alex-tymoshenko-cv.pdf" download>
        Download CV
      </a>

      <div className="timeline" aria-label="Resume highlights">
        {resumeHighlights.map((highlight, index) => (
          <article key={highlight} className="timeline-item">
            <span className="timeline-item__marker" aria-hidden="true" />
            <small>{`0${index + 1}`}</small>
            <h2>{highlight}</h2>
            <p>Detailed resume content will be added after the public CV is finalized.</p>
          </article>
        ))}
      </div>
    </section>
  );
}
