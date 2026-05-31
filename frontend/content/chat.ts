import type { QuickPrompt } from "../types/chat";

export const quickPrompts: readonly QuickPrompt[] = [
  {
    label: "Give me your 1-minute intro.",
    responses: [
      `Alex builds practical automation for business workflows, APIs, ERP systems, reporting, and dashboards.

His automation background goes back to the 2000s:
- Excel macros while working as a credit broker;
- MySQL for company operations in 2018;
- Bitrix24 ERP during the 2020 remote-work shift.

After the war in Ukraine forced his move to the UK in 2022, he focused on AI-assisted engineering, Python automation, and API integrations.

In 2024, he delivered an Odoo Enterprise API integration that reduced one employee's workload by 68%.

He also holds an MBA with honours and has a strong analytical background.

Would you like to know more about his latest work experience?`,
      `Alex combines long-term business automation experience with newer AI-assisted software development.

He started with Excel automation in the 2000s, then moved business operations into MySQL in 2018 and Bitrix24 ERP in 2020.

After the war in Ukraine forced his move to the UK in 2022, he focused more deeply on Python, AI engineering, APIs, and workflow automation.

His 2024 Odoo Enterprise API project reduced one employee's workload by 68%.

He also holds an MBA with honours and is strong in analytics, reporting, and dashboards.

Would you like a short overview of his most recent role?`,
      `Alex focuses on automation, API integrations, ERP workflows, reporting, and operational dashboards.

His practical automation path includes:
- Excel macros in the 2000s;
- moving company processes to MySQL in 2018;
- implementing Bitrix24 ERP in 2020;
- building API-based workflow automation in the UK.

After the war in Ukraine forced his move to the UK in 2022, he shifted his focus towards AI-assisted engineering and Python automation.

In 2024, he delivered an Odoo Enterprise integration that reduced one employee's workload by 68%.

Would you like the key facts from his latest work experience?`,
    ],
  },
  {
    label: "Give me a short overview of his work experience.",
    responses: [
      `Alex's career started in finance and operations:
- assistant accountant;
- economist and senior economist;
- deputy branch manager in banking;
- credit broker;
- managing director of a recruitment company.

He later helped grow that recruitment company into a regional leader.

After the war in Ukraine forced his move to the UK in late 2022, he focused more deeply on Python, AI-assisted analytics, and automation.

His first UK role was at Hydrosphere UK, where he worked as an Automation Engineer.

Would you like the key facts about his professional achievements?`,
      `Alex has a mixed business and software automation background.

His work experience includes:
- finance and accounting support;
- economist and senior economist roles;
- banking management;
- credit brokerage;
- managing a recruitment company that grew into a regional leader.

After the war in Ukraine forced his relocation to the UK in late 2022, he focused on Python, AI-assisted analytics, and workflow automation.

His first UK position was Automation Engineer at Hydrosphere UK.

Would you like a concise list of his strongest achievements?`,
      `Alex's work experience developed from finance and banking into business leadership and automation.

His earlier roles included:
- assistant accountant;
- economist and senior economist;
- deputy bank branch manager;
- credit broker;
- managing director of a recruitment company.

That recruitment company later became a regional leader.

After the war in Ukraine forced his move to the UK in 2022, he focused on Python, AI-assisted analytics, and automation.

His first UK role was Automation Engineer at Hydrosphere UK.

Would you like a summary of the most relevant achievements?`,
    ],
  },
  {
    label: "When is Alex ready to start work?",
    responses: [
      `Alex is currently freelancing, so he should usually be available relatively quickly.

I do not have access to his calendar, so the exact start date should be confirmed with him directly.

Would you like me to connect him directly?

Your details will not be passed to him at this stage, and he will not see your phone number or email unless you choose to share them.`,
      `Alex is doing freelance work, so his availability is likely to be relatively flexible.

I cannot check his calendar, so the safest answer is to ask him directly about the exact start date.

Would you like me to connect him directly?

Your contact details will not be shared with him at this stage unless you decide to provide them.`,
      `Alex should be able to discuss availability fairly quickly because he is currently freelancing.

I am not connected to his calendar, so I cannot confirm an exact start date here.

Would you like me to connect him directly?

He will not receive your phone number or email from this chat unless you choose to share those details.`,
    ],
  },
];

export const warmupMessages = [
  "Give me a second, I’m getting ready",
  "Reviewing Alex’s public profile",
  "Checking project notes",
  "Preparing a clear answer",
] as const;

export const thinkingMessages = [
  "Thinking",
  "Looking through Alex’s documents",
  "Preparing the answer",
] as const;

export const CHAT_HISTORY_LIMIT = 8;
export const CHAT_HISTORY_ITEM_MAX_CHARS = 1000;
export const CHAT_HISTORY_TOTAL_MAX_CHARS = 6000;
export const SCRIPTED_RESPONSE_DELAY_MS = 3000;
export const ESCALATION_TRANSCRIPT_LIMIT = 20;
export const ESCALATION_TRANSCRIPT_ITEM_MAX_CHARS = 2000;
export const ESCALATION_TRANSCRIPT_TOTAL_MAX_CHARS = 8000;
export const ESCALATION_CONSENT_COPY =
  "If you connect with Alex, this chat history will be shared with him so he can " +
  "understand the context. No email or phone number will be shared unless you " +
  "type it yourself.";

export const HANDOFF_CONFIRMATION_PATTERNS = [
  /^\s*(yes|yeah|yep|sure|ok|okay|confirm|i confirm|yes please|please do)\s*[.!?]*\s*$/i,
  /^\s*(да|так|ок|окей|добре|пожалуйста|будь ласка)\s*[.!?]*\s*$/i,
] as const;

export const HANDOFF_REQUEST_PATTERNS = [
  /^\s*connect\s*[.!?]*\s*$/i,
  /^\s*connect\s+me\s*[.!?]*\s*$/i,
  /\bconnect\s+(me\s+)?(with|to)\s+alex\b/i,
  /\bcan\s+you\s+connect\s+me\s+(with|to)\s+alex\b/i,
  /\bgive\s+me\s+alex\b/i,
  /\bget\s+me\s+alex\b/i,
  /\bi\s+confirm\s+i('?d| would)\s+like\s+to\s+(talk|speak|chat)\s+(to|with)\s+alex\b/i,
  new RegExp(
    String.raw`\bi\s+(want|would\s+like|need|'d\s+like)\s+(to\s+)?` +
      String.raw`(talk|speak|chat)\s+(to|with)\s+alex\b`,
    "i",
  ),
  /\b(talk|speak|chat)\s+(to|with)\s+alex\b/i,
  /\bcan\s+alex\s+(contact|call|message|email|reach)\s+me\b/i,
  /\bi('?d| would)\s+like\s+to\s+hire\s+(alex|him)\b/i,
  /\bi\s+(want|need)\s+to\s+hire\s+(alex|him)\b/i,
  /\b(best|great|strong)\s+offer\s+(for\s+)?(alex|him)\b/i,
  /\btell\s+(alex|him)\s+i\b/i,
  new RegExp(
    String.raw`\bget\s+alex\s+(to\s+)?` +
      String.raw`(contact|call|message|email|reply\s+to)\s+me\b`,
    "i",
  ),
  new RegExp(
    String.raw`\bplease\s+(connect|put)\s+me\s+` +
      String.raw`(through\s+)?(to\s+)?alex\b`,
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
  /\bсоедини\s+меня\b/i,
  /\bсоедините\s+меня\b/i,
  /\bсоедини\s+меня\s+с\s+алексом\b/i,
  /\bсоедините\s+меня\s+с\s+алексом\b/i,
  /\bпоговорить\s+с\s+алексом\b/i,
  /\bхочу\s+поговорить\s+с\s+алексом\b/i,
  /\bхочу\s+связаться\s+с\s+алексом\b/i,
  /\bхочу\s+поговорити\s+з\s+алексом\b/i,
  /\bхочу\s+зв'язатися\s+з\s+алексом\b/i,
] as const;
