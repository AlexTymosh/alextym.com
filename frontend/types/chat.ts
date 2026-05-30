export type Confidence = "low" | "medium" | "high";

export type MessageRole = "user" | "assistant" | "alex";

export type HandoffState =
  | "idle"
  | "waiting_for_alex"
  | "connected"
  | "closed"
  | "error";

export type HandoffReason = "insufficient_data" | "private_data";

export type ChatSource = {
  title: string;
  section?: string | null;
  confidence: Confidence;
};

export type ChatResponse = {
  answer: string;
  sources: ChatSource[];
  confidence: Confidence;
  not_enough_data: boolean;
  handoff_suggested?: boolean;
  handoff_reason?: HandoffReason | null;
};

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type EscalationTranscriptMessage = {
  role: "user" | "assistant";
  content: string;
};

export type EscalationResponse = {
  status: string;
  handoff_id?: string | null;
  state?: string | null;
  expires_in_seconds?: number | null;
};

export type EscalationMessageResponse = {
  status: string;
};

export type EscalationCloseResponse = {
  status: string;
  state: string;
};

export type EscalationStreamMessage = {
  id?: string;
  role?: string;
  content?: string;
  created_at?: string;
};

export type Message = {
  id: string;
  role: MessageRole;
  text: string;
  sources?: ChatSource[];
  confidence?: Confidence;
  notEnoughData?: boolean;
  handoffSuggested?: boolean;
  handoffReason?: HandoffReason | null;
};

export type QuickPrompt = {
  label: string;
  responses: readonly string[];
};
