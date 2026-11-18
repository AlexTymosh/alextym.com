import type { LabOAuthProvider } from "../lib/portfolio-lab/admission-policy";

export function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="currentColor">
      <path d="M12 .5A12 12 0 0 0 8.2 23.9c.6.1.8-.3.8-.6v-2.1c-3.3.7-4-1.4-4-1.4-.5-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 12 .5Z" />
    </svg>
  );
}

export function ProviderIcon({ provider }: { provider: LabOAuthProvider }) {
  if (provider === "github.com") return <GitHubIcon />;
  if (provider === "facebook.com") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <circle cx="12" cy="12" r="12" fill="#0866ff" />
        <path fill="#fff" d="M16.5 15.5l.5-3.5h-3.2V9.7c0-1 .5-1.9 1.9-1.9h1.4v-3s-1.3-.2-2.5-.2c-2.6 0-4.3 1.6-4.3 4.6V12H7.4v3.5h2.9v8.3h3.5v-8.3h2.7z" />
      </svg>
    );
  }
  if (provider === "microsoft.com") {
    return (
      <svg viewBox="0 0 23 23" aria-hidden="true" focusable="false">
        <rect width="11" height="11" fill="#f25022" />
        <rect x="12" width="11" height="11" fill="#7fba00" />
        <rect y="12" width="11" height="11" fill="#00a4ef" />
        <rect x="12" y="12" width="11" height="11" fill="#ffb900" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.2 3.6l6.85-6.85C35.89 2.38 30.46 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.24 5.48-4.75 7.18l7.68 5.96c4.48-4.13 7.11-10.22 7.11-17.61Z" />
      <path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.78-4.59l-7.98-6.19A23.9 23.9 0 0 0 0 24c0 3.88.93 7.54 2.55 10.78l7.98-6.19Z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.94-2.13 15.87-5.84l-7.68-5.96c-2.16 1.45-4.94 2.3-8.19 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z" />
    </svg>
  );
}
