const quickPrompts = [
  "Give me your 30-second intro.",
  "Tell me about your recent projects.",
  "How did you move from business to software development?",
];

export default function ChatPage() {
  return (
    <section className="max-w-3xl">
      <h1 className="text-3xl font-semibold">Hi, I&apos;m Alex&apos;s digital assistant.</h1>
      <p className="mt-4 text-zinc-700 dark:text-zinc-300">
        This AI is augmented by Alex&apos;s work and experiences. Ask about RAG projects or AI
        automation workflows.
      </p>
      <div className="mt-8 grid gap-3">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="rounded border border-zinc-300 px-4 py-3 text-left text-sm transition hover:border-zinc-500 dark:border-zinc-700 dark:hover:border-zinc-500"
          >
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}
