export type Privacy = {
  show_online: boolean; show_room: boolean; show_activity: boolean; show_last_seen: boolean;
  allow_friend_invites: boolean; allow_nonfriend_invites: boolean; allow_email_pings: boolean; allow_sms_pings: boolean;
};
export const privacyKeys: (keyof Privacy)[] = ["show_online", "show_room", "show_activity", "show_last_seen", "allow_friend_invites", "allow_nonfriend_invites", "allow_email_pings", "allow_sms_pings"];
export type Profile = { public_id: string; nickname: string; avatar: string };
export type Friend = Profile & { status: "incoming" | "outgoing" | "accepted" | "blocked"; presence: "hidden" | "online" | "not_in_meeting"; room?: { slug: string; name: string }; last_seen_ms?: number };
export type Notice = { id: string; sender: string; nickname: string; slug: string; text: string; created_at_ms: number; read: boolean };
export type Social = Profile & { privacy: Privacy; friends: Friend[]; favourites: string[]; recent: string[]; notices: Notice[] };
export type Person = { id: string; nickname: string; avatar: string; location: "lounge" | "table"; role: "visit" | "watch"; self: boolean };
export type Proposal = { id: string; sender: string; location: "lounge" | "table"; role: "visit" | "watch" | "play"; responses: Record<string, "pending" | "accepted" | "declined" | "expired" | "cancelled"> };
export type Snapshot = { type: "room.snapshot"; protocol_version: 1; room_id: string; server_now_ms: number; meeting_id: string; sequence: number; chat_revision: number; room_revision: number; inbox_revision: number; people: Person[]; proposals: Proposal[] };
export type ChatMessage = { id: string; sender: string; nickname: string; text: string; created_at_ms: number };
export type ChatPage = { messages: ChatMessage[]; before: string | null };
export type Channel = "internal" | "email" | "sms";
export type Recipient = Profile & { channels: Channel[] };
