import Image from "next/image";
import Link from "next/link";

import type { FeaturedProjectPreviewItem } from "../content/home";
import {
  assistantCard,
  buildFocus,
  featuredAutomationDemo,
  featuredProject,
  profileCard,
  projectStack,
} from "../content/home";
import styles from "./page.module.css";

const projectPreviewSlotClassNames: Record<FeaturedProjectPreviewItem["slot"], string> = {
  "top-left": styles.projectPreviewTileTopLeft,
  "top-right": styles.projectPreviewTileTopRight,
  "bottom-right": styles.projectPreviewTileBottomRight,
};

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" role="img">
      <path d="M12 .5A12 12 0 0 0 8.2 23.9c.6.1.8-.3.8-.6v-2.1c-3.3.7-4-1.4-4-1.4-.5-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg viewBox="0 0 24 24" role="img">
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33 0-3.04-1.85-3.04s-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05a3.75 3.75 0 0 1 3.37-1.85c3.6 0 4.27 2.37 4.27 5.45v6.29ZM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13Zm1.78 13.02H3.56V9h3.56v11.45ZM22.23 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.8 24 1.77 24h20.46c.98 0 1.77-.77 1.77-1.73V1.73C24 .77 23.2 0 22.23 0Z" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg viewBox="0 0 24 24" role="img">
      <path d="M24 12.07C24 5.43 18.63.06 12 .06S0 5.43 0 12.07c0 6 4.39 10.98 10.13 11.88v-8.4H7.08v-3.48h3.05V9.42c0-3.01 1.79-4.67 4.53-4.67 1.31 0 2.68.23 2.68.23v2.95h-1.5c-1.49 0-1.96.93-1.96 1.88v2.26h3.33l-.53 3.48h-2.8v8.4A12.02 12.02 0 0 0 24 12.07Z" />
    </svg>
  );
}

function getYouTubeEmbedUrl(videoId: string) {
  return `https://www.youtube-nocookie.com/embed/${videoId}`;
}

function getYouTubeWatchUrl(videoId: string) {
  return `https://www.youtube.com/watch?v=${videoId}`;
}

function isExternalUrl(href: string) {
  return href.startsWith("http://") || href.startsWith("https://");
}

function FeaturedProjectCta() {
  if (isExternalUrl(featuredProject.href)) {
    return (
      <a className="primary-link" href={featuredProject.href} target="_blank" rel="noreferrer">
        {featuredProject.cta}
      </a>
    );
  }

  return (
    <Link href={featuredProject.href} className="primary-link">
      {featuredProject.cta}
    </Link>
  );
}

function ProjectPreviewTitle({ item }: { item: FeaturedProjectPreviewItem }) {
  if (isExternalUrl(item.href)) {
    return (
      <a href={item.href} target="_blank" rel="noreferrer">
        {item.title}
      </a>
    );
  }

  return <Link href={item.href}>{item.title}</Link>;
}

export default function HomePage() {
  const youtubeEmbedUrl = getYouTubeEmbedUrl(featuredAutomationDemo.youtubeVideoId);
  const youtubeWatchUrl = getYouTubeWatchUrl(featuredAutomationDemo.youtubeVideoId);

  return (
    <section className="home-grid" aria-label="Alex Tymoshenko portfolio overview">
      <article className="card profile-card">
        <div className={`avatar-mark ${styles.profileImageFrame}`} aria-hidden="true">
          <Image
            src={profileCard.imageSrc}
            alt={profileCard.imageAlt}
            width={208}
            height={208}
            className={styles.profileImage}
            priority
          />
        </div>
        <div>
          <h1>{profileCard.name}</h1>
          <p>{profileCard.summary}</p>
        </div>
      </article>

      <article className="card accent-card">
        <p className="eyebrow">{assistantCard.eyebrow}</p>
        <div className="mini-chat" aria-hidden="true">
          <strong>{assistantCard.title}</strong>
          <span>{assistantCard.description}</span>
        </div>
        <Link href={assistantCard.href} className="text-link">
          {assistantCard.cta}
        </Link>
      </article>

      <article className="card connect-card">
        <p className="eyebrow">Connect</p>
        <div className="social-row">
          <a href="https://github.com/AlexTymosh" target="_blank" rel="noreferrer" aria-label="GitHub">
            <GitHubIcon />
          </a>
          <a
            href="https://www.facebook.com/ol.tymoshenko"
            target="_blank"
            rel="noreferrer"
            aria-label="Facebook"
          >
            <FacebookIcon />
          </a>
          <a
            href="https://www.linkedin.com/in/alex-tim-tech/"
            target="_blank"
            rel="noreferrer"
            aria-label="LinkedIn"
          >
            <LinkedInIcon />
          </a>
        </div>
      </article>

      <article className={`card list-card ${styles.portfolioCard}`}>
        <div className={styles.projectPreview}>
          <div className={styles.projectPreviewHeading}>{featuredProject.previewHeading}</div>
          <div className={styles.projectPreviewGrid}>
            {featuredProject.previewItems.map((item) => (
              <div
                key={item.title}
                className={`${styles.projectPreviewTile} ${projectPreviewSlotClassNames[item.slot]}`}
              >
                {item.imageSrc ? (
                  <Image
                    src={item.imageSrc}
                    alt={item.imageAlt ?? ""}
                    fill
                    sizes="(max-width: 860px) 50vw, 240px"
                    className={styles.projectPreviewImage}
                  />
                ) : null}
                <div className={styles.projectPreviewTileCopy}>
                  <strong>
                    <ProjectPreviewTitle item={item} />
                  </strong>
                  <span>{item.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.portfolioCopy}>
          <h2>{featuredProject.title}</h2>
          <div className={styles.portfolioDescription}>
            {featuredProject.description.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
          <FeaturedProjectCta />
        </div>
      </article>

      <article className={`card list-card ${styles.videoCard}`}>
        <p className="eyebrow">{featuredAutomationDemo.eyebrow}</p>

        <div className={styles.videoFrame}>
          <iframe
            src={youtubeEmbedUrl}
            title={featuredAutomationDemo.youtubeTitle}
            loading="lazy"
            allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>

        <div className={styles.videoCopy}>
          <h2>{featuredAutomationDemo.title}</h2>
          <p>{featuredAutomationDemo.description}</p>
          <a className="text-link" href={youtubeWatchUrl} target="_blank" rel="noreferrer">
            {featuredAutomationDemo.cta}
          </a>
        </div>
      </article>

      <article className={`card wide-card ${styles.buildFocusCard}`}>
        <p className="eyebrow">{buildFocus.eyebrow}</p>

        <div className={styles.buildFocusCopy}>
          <h2>{buildFocus.title}</h2>
          <p>{buildFocus.description}</p>
        </div>

        <div className={styles.embeddedStack}>
          <p className="eyebrow">Project Stack</p>
          <div className="tag-cloud">
            {projectStack.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
      </article>
    </section>
  );
}
