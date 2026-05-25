import Link from "next/link";

const softwareItems = [
  ["FastAPI backend", "Python / API"],
  ["Next.js frontend", "TypeScript"],
  ["RAG pipeline", "Qdrant / LLM"],
  ["Automation workflows", "Process design"],
];

const techStack = ["Python", "FastAPI", "Next.js", "TypeScript", "Tailwind", "Docker", "Qdrant", "RAG"];

const focusAreas = [
  ["AI portfolio", "Personal assistant"],
  ["Backend systems", "FastAPI"],
  ["Workflow automation", "Operations"],
  ["Business to software", "Career transition"],
];

export default function HomePage() {
  return (
    <section className="home-grid" aria-label="Alex Tymoshenko portfolio overview">
      <article className="card profile-card">
        <div className="avatar-mark" aria-hidden="true">
          AT
        </div>
        <div>
          <p className="eyebrow">Software Engineer</p>
          <h1>Alex Tymoshenko</h1>
          <p>
            Building practical AI automation, RAG-based assistants, and deploy-ready web
            applications with FastAPI and Next.js.
          </p>
        </div>
      </article>

      <article className="card accent-card">
        <p className="eyebrow">Digital Assistant</p>
        <div className="mini-chat" aria-hidden="true">
          <strong>Hi, I&apos;m Alex&apos;s digital assistant.</strong>
          <span>Ask about projects, stack, and automation workflows.</span>
        </div>
        <Link href="/chat" className="text-link">
          Talk to assistant
        </Link>
      </article>

      <article className="card connect-card">
        <p className="eyebrow">Connect</p>
        <div className="social-row">
          <a href="https://www.linkedin.com/in/alex-tim-tech/" target="_blank" rel="noreferrer">
            in
          </a>
          <a href="https://github.com/AlexTymosh" target="_blank" rel="noreferrer">
            gh
          </a>
          <a href="https://www.facebook.com/ol.tymoshenko" target="_blank" rel="noreferrer">
            fb
          </a>
        </div>
        <Link href="/contact" className="text-link">
          Contact page
        </Link>
      </article>

      <article className="card feature-card">
        <div className="feature-preview" aria-hidden="true">
          <div className="preview-bar" />
          <div className="preview-grid">
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
        <div className="feature-card__copy">
          <p className="eyebrow">Featured Project</p>
          <h2>alextym.com</h2>
          <p>
            A personal AI portfolio with a FastAPI backend, Next.js frontend, warm-up flow, and a
            planned RAG knowledge base.
          </p>
          <Link href="/chat" className="primary-link">
            Open Chat
          </Link>
        </div>
      </article>

      <article className="card list-card">
        <p className="eyebrow">AI & Software</p>
        <div className="stack-list">
          {softwareItems.map(([name, tag]) => (
            <div key={name} className="stack-list__item">
              <span>{name}</span>
              <small>{tag}</small>
            </div>
          ))}
        </div>
      </article>

      <article className="card tags-card">
        <p className="eyebrow">Tech Stack</p>
        <div className="tag-cloud">
          {techStack.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </article>

      <article className="card wide-card">
        <p className="eyebrow">Focus Areas</p>
        <div className="focus-grid">
          {focusAreas.map(([title, subtitle]) => (
            <div key={title}>
              <strong>{title}</strong>
              <span>{subtitle}</span>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
