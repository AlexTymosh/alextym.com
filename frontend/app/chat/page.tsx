import type { Metadata } from "next";
import { ChatShell } from "../../components/chat-shell";
import { getSeoPage } from "../../lib/project-config";

const chatSeo = getSeoPage("chat");

export const metadata: Metadata = {
  title: chatSeo.title,
  description: chatSeo.description,
  alternates: {
    canonical: chatSeo.canonical,
  },
};

export default function ChatPage() {
  return (
    <div className="chat-page">
      <ChatShell />
    </div>
  );
}
