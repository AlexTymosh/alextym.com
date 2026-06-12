"use client";

import { useMemo, useState } from "react";

import styles from "./page.module.css";

export type CaseStudyDocument = {
  id: string;
  label: string;
  eyebrow: string;
  title: string;
  description: string;
  path: string;
};

type DocumentSwitcherProps = {
  documents: CaseStudyDocument[];
};

export function DocumentSwitcher({ documents }: DocumentSwitcherProps) {
  const [activeDocumentId, setActiveDocumentId] = useState(documents[0]?.id ?? "");

  const activeDocument = useMemo(
    () => documents.find((document) => document.id === activeDocumentId) ?? documents[0],
    [activeDocumentId, documents],
  );

  if (!activeDocument) {
    return null;
  }

  return (
    <section className={styles.viewerSection} aria-labelledby="pdf-preview-title">
      <div className={styles.viewerHeader}>
        <div className={styles.viewerIntro}>
          <p className="eyebrow">{activeDocument.eyebrow}</p>
          <h2 id="pdf-preview-title">{activeDocument.title}</h2>
          <p>{activeDocument.description}</p>
        </div>

        <div className={styles.documentTabs} role="tablist" aria-label="Case study documents">
          {documents.map((document) => {
            const isActive = document.id === activeDocument.id;

            return (
              <button
                key={document.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                aria-controls="case-study-pdf-panel"
                className={styles.documentTab}
                onClick={() => setActiveDocumentId(document.id)}
              >
                {document.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className={styles.pdfFrame} id="case-study-pdf-panel" role="tabpanel">
        <iframe
          key={activeDocument.id}
          src={`${activeDocument.path}#toolbar=1&navpanes=0`}
          title={`${activeDocument.title} PDF preview`}
          loading="lazy"
        />
      </div>
    </section>
  );
}
