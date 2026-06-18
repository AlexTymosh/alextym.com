import type { Metadata } from "next";
import { ContactForm } from "../../components/contact-form";
import {
  contactConfig,
  getPublicLinks,
  getSeoPage,
} from "../../lib/project-config";

const contactSeo = getSeoPage("contact");

export const metadata: Metadata = {
  title: contactSeo.title,
  description: contactSeo.description,
  alternates: {
    canonical: contactSeo.canonical,
  },
};

const socialLinks = getPublicLinks(contactConfig.socialLinks);

export default function ContactPage() {
  return (
    <section className="contact-page">
      <div className="contact-heading">
        <h1>{contactConfig.heading.title}</h1>
        <p>{contactConfig.heading.description}</p>
        <div className="contact-links" aria-label="Social links">
          {socialLinks.map((link) => (
            <a key={link.key} href={link.href} target="_blank" rel="noreferrer">
              {link.label}
            </a>
          ))}
        </div>
      </div>

      <ContactForm />
    </section>
  );
}
