import type { Metadata } from "next";
import { ChatShell } from "../../components/chat-shell";

export const metadata: Metadata = {
  title: "AI Profile Chat",
  description:
    "Ask Alex Tymoshenko's AI profile assistant about his projects, CV, " +
    "automation experience, Python, FastAPI, and RAG portfolio work.",
  alternates: {
    canonical: "/chat",
  },
};

export default function ChatPage() {
  return (
    <div className="chat-page">
      <ChatShell />
    </div>
  );
}
