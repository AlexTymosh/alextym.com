import { chatConfig, ownerConfig } from "../lib/project-config";
import type { QuickPrompt } from "../types/chat";

const ownerName = ownerConfig.shortName;
const ownerPossessiveName = ownerConfig.possessiveName;
const ownerTermPattern = buildOwnerTermPattern();

export const chatShellCopy = {
  ariaLabel: "AI digital assistant",
  contactFormLinkLabel: "Open the contact form",
  closedInputPlaceholder: "Ask my assistant anything or request a new connection...",
  defaultInputPlaceholder: "Ask my assistant anything...",
  handoffActionsAriaLabel: "Handoff actions",
  handoffCloseLabel: `End handoff with ${ownerName}`,
  handoffClosedStatus: "Handoff closed",
  handoffClosingLabel: "Closing...",
  handoffConnectLabel: `Connect me with ${ownerName}`,
  handoffConnectedStatus: `${ownerName} is connected`,
  handoffConnectingLabel: "Connecting...",
  handoffContinueLabel: "Continue with AI",
  handoffInputPlaceholder: `Message ${ownerName} through this chat...`,
  handoffPromptAriaLabel: `Connect with ${ownerName}`,
  handoffPromptTitle: `Would you like to connect with ${ownerName}?`,
  handoffReconnectingStatus: "Handoff reconnecting",
  handoffWaitingStatus: `Waiting for ${ownerName}`,
  inputAriaLabel: `Ask ${ownerPossessiveName} AI assistant`,
  introDescription: `Ask about ${ownerPossessiveName} public profile, work experience, automation projects, and availability.`,
  introTitle: `Hi, I'm ${ownerPossessiveName} AI assistant.`,
  messageSenderOwner: ownerName,
  quickPromptsAriaLabel: "Quick prompts",
  readyStatus: "Ready",
  resetLabel: "Reset chat",
  sendLabel: "Send message",
  sourceLabel: "Sources",
  title: `${ownerPossessiveName} AI Assistant`,
  warmupUnavailableStatus: "Warm-up unavailable",
} as const;
export const chatHandoffCopy = {
  closedByUserMessage:
    "This handoff has been closed. New messages will go to the AI assistant unless you request a new connection.",
  closeFailureMessage: "Could not close this handoff right now. Please try again later.",
  connectFailureMessage: `Could not connect with ${ownerName} right now. Please try again later.`,
  connectionDailyLimitMessage:
    "You've reached the daily limit for connection requests. Please try again later.",
  consentCopy: `If you connect with ${ownerName}, this chat history will be shared with them so they can understand the context. No email or phone number will be shared unless you type it yourself.`,
  defaultUnavailableMessage:
    "Live handoff is currently outside its configured availability window. Please try again during those hours or use the contact form.",
  messageDailyLimitMessage:
    "You've reached the daily limit for handoff messages. Please try again later.",
  nameRequestMessage: `${ownerName} has been notified and can review this chat for context.\n\nWhile ${ownerName} is getting ready to answer, could you tell me how I should address you?`,
  notificationSentMessage: `${ownerName} has been notified and will be able to review this chat for context.`,
  reconnectingNotice:
    "The live handoff connection is reconnecting. Please keep this page open.",
  sendFailureMessage: `Could not send this message to ${ownerName} right now. Please try again later.`,
  sessionClosedMessage:
    "This handoff session has closed. New messages go back to the AI assistant.",
  sessionExpiredMessage: `This handoff session has expired. You can continue with the AI assistant or request a new connection with ${ownerName}.`,
  unavailableRetryLine:
    "Please try again during those hours or use the contact form.",
} as const;
export const chatNoticeCopy = {
  assistantErrorMessage: "Something went wrong. Please try again later.",
  assistantUnavailable: "The assistant is temporarily unavailable.",
  streamingEndedEarly: "The streaming response ended before completion.",
  streamingFallbackUsed:
    "Streaming was unavailable, so the JSON fallback was used.",
  warmupUnavailable:
    "Backend warm-up is unavailable in this environment. The assistant may still respond.",
} as const;
export const quickPrompts =
  chatConfig.quickPrompts as readonly QuickPrompt[];
export const warmupMessages = [
  "Starting the assistant",
  `Loading ${ownerPossessiveName} profile`,
  "Getting ready to chat",
] as const;
export const thinkingMessages = [
  "Understanding your question",
  `Checking ${ownerPossessiveName} profile`,
  "Preparing a grounded answer",
] as const;

export const CHAT_HISTORY_LIMIT = 8;
export const CHAT_HISTORY_ITEM_MAX_CHARS = 1000;
export const CHAT_HISTORY_TOTAL_MAX_CHARS = 6000;
export const SCRIPTED_RESPONSE_DELAY_MS = 3000;
export const ESCALATION_TRANSCRIPT_LIMIT = 20;
export const ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS = 2000;
export const ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS = 8000;
export const ESCALATION_CONSENT_COPY = chatHandoffCopy.consentCopy;

export const HANDOFF_CONFIRMATION_PATTERNS = [
  /^\s*(yes|yeah|yep|sure|ok|okay|confirm|i confirm|yes please|please do)\s*[.!?]*\s*$/i,
  new RegExp(
    String.raw`^\s*(\u0434\u0430|\u0442\u0430\u043a|\u043e\u043a|` +
      String.raw`\u043e\u043a\u0435\u0439|\u0434\u043e\u0431\u0440\u0435|` +
      String.raw`\u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430|` +
      String.raw`\u0431\u0443\u0434\u044c\s+\u043b\u0430\u0441\u043a\u0430)` +
      String.raw`\s*[.!?]*\s*$`,
    "i",
  ),
] as const;

export const HANDOFF_REQUEST_PATTERNS = [
  /^\s*connect\s*[.!?]*\s*$/i,
  /^\s*con+ect\s*[.!?]*\s*$/i,
  /^\s*con+ect\s+me\s*[.!?]*\s*$/i,
  new RegExp(String.raw`\bcon+ect\s+(me\s+)?(with|to)\s+${ownerTermPattern}\b`, "i"),
  /^\s*connect\s+me\s*[.!?]*\s*$/i,
  new RegExp(String.raw`\bconnect\s+(me\s+)?(with|to)\s+${ownerTermPattern}\b`, "i"),
  new RegExp(
    String.raw`\bcan\s+you\s+connect\s+me\s+(with|to)\s+${ownerTermPattern}\b`,
    "i",
  ),
  new RegExp(String.raw`\bgive\s+me\s+${ownerTermPattern}\b`, "i"),
  new RegExp(String.raw`\bget\s+me\s+${ownerTermPattern}\b`, "i"),
  new RegExp(
    String.raw`\bi\s+confirm\s+i('?d| would)\s+like\s+to\s+` +
      String.raw`(talk|speak|chat)\s+(to|with)\s+${ownerTermPattern}\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bi\s+(want|would\s+like|need|'d\s+like)\s+(to\s+)?` +
      String.raw`(talk|speak|chat)\s+(to|with)\s+${ownerTermPattern}\b`,
    "i",
  ),
  new RegExp(String.raw`\b(talk|speak|chat)\s+(to|with)\s+${ownerTermPattern}\b`, "i"),
  new RegExp(
    String.raw`\bcan\s+${ownerTermPattern}\s+(contact|call|message|email|reach)\s+me\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bi('?d| would)\s+like\s+to\s+hire\s+(${ownerTermPattern}|him|them)\b`,
    "i",
  ),
  new RegExp(String.raw`\bi\s+(want|need)\s+to\s+hire\s+(${ownerTermPattern}|him|them)\b`, "i"),
  new RegExp(String.raw`\b(best|great|strong)\s+offer\s+(for\s+)?(${ownerTermPattern}|him|them)\b`, "i"),
  new RegExp(String.raw`\btell\s+(${ownerTermPattern}|him|them)\s+i\b`, "i"),
  /\bshare\s+code\b/i,
  /\bright-to-work\s+share\s+code\b/i,
  /\buk\s+share\s+code\b/i,
  new RegExp(
    String.raw`\bget\s+${ownerTermPattern}\s+(to\s+)?` +
      String.raw`(contact|call|message|email|reply\s+to)\s+me\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bplease\s+(connect|put)\s+me\s+` +
      String.raw`(through\s+)?(to\s+)?${ownerTermPattern}\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bi\s+(want|would\s+like|need)\s+(to\s+)?` +
      String.raw`(talk|speak|chat)\s+(to|with)\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b(talk|speak|chat)\s+(to|with)\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b(connect|handoff|escalate)\s+(me\s+)?(to\s+)?` +
      String.raw`(a\s+)?(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bconnect\s+me\s+with\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bi\s+need\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bcan\s+i\s+(talk|speak|chat)\s+(to|with)\s+(a\s+)?` +
      String.raw`(human|person|real\s+person|agent|representative)\b`,
    "i",
  ),
  /^\s*(human|person|real\s+person|agent|representative|operator)\s*[.!?]*\s*$/i,
  new RegExp(String.raw`\b\u0441\u043e\u0435\u0434\u0438\u043d\u0438\s+\u043c\u0435\u043d\u044f\b`, "i"),
  new RegExp(String.raw`\b\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u0435\s+\u043c\u0435\u043d\u044f\b`, "i"),
  new RegExp(
    String.raw`\b\u0441\u043e\u0435\u0434\u0438\u043d\u0438\s+\u043c\u0435\u043d\u044f\s+` +
      String.raw`\u0441\s+\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u0435\s+` +
      String.raw`\u043c\u0435\u043d\u044f\s+\u0441\s+` +
      String.raw`\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c\s+` +
      String.raw`\u0441\s+\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b\u0445\u043e\u0447\u0443\s+` +
      String.raw`\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c\s+` +
      String.raw`\u0441\s+\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b\u0445\u043e\u0447\u0443\s+` +
      String.raw`\u0441\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f\s+` +
      String.raw`\u0441\s+\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b\u0445\u043e\u0447\u0443\s+` +
      String.raw`\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0438\s+` +
      String.raw`\u0437\s+\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
  new RegExp(
    String.raw`\b\u0445\u043e\u0447\u0443\s+` +
      String.raw`\u0437\u0432'\u044f\u0437\u0430\u0442\u0438\u0441\u044f\s+` +
      String.raw`\u0437\s+\u0430\u043b\u0435\u043a\u0441\u043e\u043c\b`,
    "i",
  ),
] as const;

function buildOwnerTermPattern() {
  const ownerTerms = [
    ownerName,
    ownerConfig.displayName,
    ...ownerConfig.publicAliases,
  ]
    .map((term) => term.trim())
    .filter(Boolean)
    .map(escapeRegExp);

  return `(?:${Array.from(new Set(ownerTerms)).join("|")})`;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
