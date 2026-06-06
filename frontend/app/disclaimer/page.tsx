import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Disclaimer",
  description:
    "Disclaimer for the portfolio website, AI assistant, contact flow, " +
    "human handoff, analytics, and monitoring boundaries.",
  alternates: {
    canonical: "/disclaimer",
  },
};

export default function DisclaimerPage() {
  return (
    <article className="page-panel disclaimer-page">
      <p className="eyebrow">Disclaimer</p>
      <h1>Website, AI assistant, and monitoring disclaimer</h1>

      <section>
        <h2>Purpose</h2>
        <p>
          This website and its AI assistant are provided for informational and
          portfolio demonstration purposes. They are not a guarantee of
          availability, professional certification, legal advice, immigration
          advice, financial advice, medical advice, or any other regulated
          professional advice.
        </p>
      </section>

      <section>
        <h2>AI assistant limitations</h2>
        <p>
          The assistant is designed to answer questions from reviewed public
          professional context. It can be incomplete or wrong. If it does not
          have enough information, it should say so and suggest direct contact
          instead of inventing facts.
        </p>
      </section>

      <section>
        <h2>Do not submit sensitive information</h2>
        <p>
          Do not submit passwords, API keys, payment details, private tokens,
          medical information, legal case details, home addresses, confidential
          employer/client data, or personal data about other people through the
          chat, contact form, or handoff flow.
        </p>
      </section>

      <section>
        <h2>Human handoff</h2>
        <p>
          If a visitor confirms human handoff, relevant chat context may be sent
          to the website owner through Telegram so the owner can reply. Do not
          start handoff with sensitive third-party personal data or confidential
          business information.
        </p>
      </section>

      <section>
        <h2>Analytics and monitoring</h2>
        <p>
          The project uses operational metrics and privacy-safe aggregate product
          metrics. These metrics are intended to monitor reliability and broad
          usage signals. They are not intended to profile individual visitors.
        </p>
        <p>
          The project intentionally avoids visitor IDs, user IDs, analytics
          cookies, localStorage tracking IDs, IP hashes, User-Agent hashes, raw
          referrers, query strings, and per-user chat usage metrics.
        </p>
      </section>

      <section>
        <h2>Reuse</h2>
        <p>
          The codebase may be reused according to its license, but personal
          profile content, resume content, SEO metadata, screenshots, public CV
          files, video IDs, and RAG knowledge examples should be replaced before
          reuse for another person or organisation.
        </p>
      </section>
    </article>
  );
}
