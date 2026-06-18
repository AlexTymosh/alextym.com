import type { Metadata } from "next";
import { disclaimerConfig, getSeoPage } from "../../lib/project-config";

const disclaimerSeo = getSeoPage("disclaimer");

export const metadata: Metadata = {
  title: disclaimerSeo.title,
  description: disclaimerSeo.description,
  alternates: {
    canonical: disclaimerSeo.canonical,
  },
};

export default function DisclaimerPage() {
  return (
    <article className="page-panel disclaimer-page">
      <h1>{disclaimerConfig.title}</h1>

      {renderDisclaimerBody(disclaimerConfig.bodyMarkdown)}
    </article>
  );
}

function renderDisclaimerBody(bodyMarkdown: string) {
  return bodyMarkdown
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block, index) => {
      if (block.startsWith("## ")) {
        return <h2 key={`${index}-${block}`}>{block.slice(3).trim()}</h2>;
      }

      return <p key={`${index}-${block}`}>{block}</p>;
    });
}
