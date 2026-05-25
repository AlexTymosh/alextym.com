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
        <p>
          This form is a Stage 2 UI placeholder. Backend validation and email delivery will be
          connected in the contact stage.
        </p>
        <div className="contact-links" aria-label="Social links">
          {socialLinks.map((link) => (
            <a key={link.href} href={link.href} target="_blank" rel="noreferrer">
              {link.label}
            </a>
          ))}
        </div>
      </div>

      <form className="contact-form" aria-label="Contact form placeholder">
        <label>
          <span>Your Name</span>
          <input name="name" type="text" placeholder="Your name" />
        </label>
        <label>
          <span>Email Address</span>
          <input name="email" type="email" placeholder="you@example.com" />
        </label>
        <label>
          <span>Message</span>
          <textarea name="message" rows={6} placeholder="Tell Alex what you would like to discuss." />
        </label>
        <button type="button" className="primary-link">
          Form placeholder
        </button>
      </form>
    </section>
  );
}
