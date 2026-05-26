"use client";

import { FormEvent, useMemo, useState } from "react";

type SubmitStatus = "idle" | "sending" | "success" | "error";

const initialFormState = {
  name: "",
  email: "",
  message: "",
  companyWebsite: "",
};

export function ContactForm() {
  const [formState, setFormState] = useState(initialFormState);
  const [status, setStatus] = useState<SubmitStatus>("idle");
  const [notice, setNotice] = useState<string | null>(null);

  const isSending = status === "sending";
  const statusTone = useMemo(() => {
    if (status === "success") {
      return "success";
    }

    if (status === "error") {
      return "error";
    }

    return "neutral";
  }, [status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload = {
      name: formState.name.trim(),
      email: formState.email.trim(),
      message: formState.message.trim(),
      company_website: formState.companyWebsite.trim(),
    };

    if (!payload.name || !payload.email || !payload.message) {
      setStatus("error");
      setNotice("Please fill in your name, email, and message.");
      return;
    }

    setStatus("sending");
    setNotice(null);

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(await getContactErrorMessage(response));
      }

      setFormState(initialFormState);
      setStatus("success");
      setNotice("Message sent. Alex will review it.");
    } catch (error) {
      setStatus("error");
      setNotice(error instanceof Error ? error.message : "Could not send message.");
    }
  }

  return (
    <form className="contact-form" aria-label="Contact form" onSubmit={handleSubmit}>
      <label>
        <span>Your Name</span>
        <input
          name="name"
          type="text"
          placeholder="Your name"
          autoComplete="name"
          maxLength={120}
          required
          value={formState.name}
          disabled={isSending}
          onChange={(event) =>
            setFormState((current) => ({ ...current, name: event.target.value }))
          }
        />
      </label>
      <label>
        <span>Email Address</span>
        <input
          name="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          maxLength={254}
          required
          value={formState.email}
          disabled={isSending}
          onChange={(event) =>
            setFormState((current) => ({ ...current, email: event.target.value }))
          }
        />
      </label>
      <label>
        <span>Message</span>
        <textarea
          name="message"
          rows={6}
          placeholder="Tell Alex what you would like to discuss."
          maxLength={4000}
          required
          value={formState.message}
          disabled={isSending}
          onChange={(event) =>
            setFormState((current) => ({ ...current, message: event.target.value }))
          }
        />
      </label>
      <label className="contact-form__honeypot" aria-hidden="true">
        <span>Company Website</span>
        <input
          name="company_website"
          type="text"
          autoComplete="off"
          tabIndex={-1}
          value={formState.companyWebsite}
          onChange={(event) =>
            setFormState((current) => ({ ...current, companyWebsite: event.target.value }))
          }
        />
      </label>
      <button type="submit" className="primary-link contact-form__submit" disabled={isSending}>
        {isSending ? "Sending..." : "Send Message"}
      </button>
      {notice ? (
        <p className={`contact-form__notice contact-form__notice--${statusTone}`} role="status">
          {notice}
        </p>
      ) : null}
    </form>
  );
}

async function getContactErrorMessage(response: Response): Promise<string> {
  if (response.status === 429) {
    return "Daily message limit reached. Please try again later.";
  }

  if (response.status === 422) {
    return "Please check the form fields and try again.";
  }

  if (response.status === 503) {
    return "Contact form is temporarily unavailable. Please try again later.";
  }

  if (response.status >= 500) {
    return "Could not send message. Please try again later.";
  }

  return "Could not send message. Please try again later.";
}
