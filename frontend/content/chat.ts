import { chatConfig, ownerConfig } from "../lib/project-config";
import type { QuickPrompt } from "../types/chat";

const ownerName = ownerConfig.shortName;
const ownerPossessiveName = ownerConfig.possessiveName;

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
  handoffDismissLabel: "Not now",
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

export const CHAT_HISTORY_LIMIT = 10;
export const CHAT_HISTORY_ITEM_MAX_CHARS = 2000;
export const CHAT_HISTORY_TOTAL_MAX_CHARS = 6000;
export const SCRIPTED_RESPONSE_DELAY_MS = 3000;
export const ESCALATION_TRANSCRIPT_LIMIT = 20;
export const ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS = 2000;
export const ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS = 8000;
export const ESCALATION_CONSENT_COPY = chatHandoffCopy.consentCopy;
