import { ContactForm } from "../../components/contact-form";

const socialLinks = [
  { label: "LinkedIn", href: "https://www.linkedin.com/in/alex-tim-tech/" },
  { label: "GitHub", href: "https://github.com/AlexTymosh" },
  { label: "Facebook", href: "https://www.facebook.com/ol.tymoshenko" },
];

export default function ContactPage() {
  return (
    <section className="contact-page">
      <div className="contact-heading">
        <h1>Contact Me</h1>
        <p>For hiring, collaboration, or project conversations, send a short note.</p>
        <div className="contact-links" aria-label="Social links">
          {socialLinks.map((link) => (
            <a key={link.href} href={link.href} target="_blank" rel="noreferrer">
              {link.label}
            </a>
          ))}
        </div>
      </div>

      <ContactForm />
    </section>
  );
}
