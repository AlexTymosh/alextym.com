"use client";

import { FormEvent, useMemo, useState } from "react";
import { contactConfig } from "../lib/project-config";

type SubmitStatus = "idle" | "sending" | "success" | "error";

const initialFormState = {
  name: "",
  email: "",
  message: "",
  companyWebsite: "",
};

export function ContactForm() {
  const formCopy = contactConfig.form;
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
      setNotice(formCopy.notices.missingFields);
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
      setNotice(formCopy.notices.success);
    } catch (error) {
      setStatus("error");
      setNotice(
        error instanceof Error ? error.message : formCopy.notices.genericError,
      );
    }
  }

  return (
    <form className="contact-form" aria-label={formCopy.ariaLabel} onSubmit={handleSubmit}>
      <label>
        <span>{formCopy.fields.name.label}</span>
        <input
          name="name"
          type="text"
          placeholder={formCopy.fields.name.placeholder}
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
        <span>{formCopy.fields.email.label}</span>
        <input
          name="email"
          type="email"
          placeholder={formCopy.fields.email.placeholder}
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
        <span>{formCopy.fields.message.label}</span>
        <textarea
          name="message"
          rows={6}
          placeholder={formCopy.fields.message.placeholder}
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
        <span>{formCopy.fields.companyWebsite.label}</span>
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
        {isSending ? formCopy.sendingLabel : formCopy.submitLabel}
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
    return contactConfig.form.notices.dailyLimit;
  }

  if (response.status === 422) {
    return contactConfig.form.notices.validationError;
  }

  if (response.status === 503) {
    return contactConfig.form.notices.unavailable;
  }

  if (response.status >= 500) {
    return contactConfig.form.notices.serverError;
  }

  return contactConfig.form.notices.serverError;
}
