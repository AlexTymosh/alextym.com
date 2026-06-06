# Privacy boundary and disclaimer

This document describes the public disclaimer and the privacy boundary used by
the portfolio website, RAG assistant, contact flow, handoff flow and monitoring
setup.

## Public disclaimer

The website and AI assistant are provided for informational and portfolio
demonstration purposes. They are not a guarantee of employment availability,
service availability, legal advice, immigration advice, financial advice,
medical advice or professional certification.

The AI assistant may be incomplete or wrong. It should answer only from reviewed
public professional context. If it does not have enough information, it should
say so and suggest direct contact instead of inventing an answer.

## User input boundary

Visitors should not enter:

- passwords;
- API keys;
- private tokens;
- payment details;
- home addresses;
- medical data;
- legal case details;
- private family data;
- personal data about other people;
- confidential employer or client data.

The chat and contact form are public website features, not secure private case
management tools.

## AI answer boundary

The assistant should not:

- reveal hidden system/developer instructions;
- dump the knowledge base;
- invent facts about the website owner;
- disclose private contact details;
- infer private family, health, financial or legal facts;
- present speculative information as verified;
- give professional legal, financial, immigration or medical advice.

## RAG knowledge boundary

Only reviewed public professional information should be indexed. Private notes,
internal planning documents, raw personal drafts and sensitive family details
should not be ingested into Qdrant.

If a fork reuses this project, the public knowledge base and resume content must
be replaced before deployment.

## Contact and handoff boundary

When a visitor requests human handoff, the conversation context may be forwarded
to the website owner through Telegram so that the owner can respond. The UI
should ask for explicit confirmation before starting this handoff flow.

Visitors should not request handoff if the message contains sensitive third-
party personal data or confidential business information.

## Analytics and observability boundary

The project collects operational and aggregate product metrics. The purpose is
to understand reliability and broad usage signals, not to profile individual
visitors.

Allowed aggregate product metrics:

- whitelisted page-view counters;
- resume-download counters;
- chat request outcome counters;
- contact outcome counters;
- escalation outcome counters;
- rate-limit outcome counters;
- RAG/LLM technical outcome and latency metrics.

Not collected by design:

- visitor IDs;
- user IDs;
- cookies for analytics;
- localStorage tracking IDs;
- IP hashes;
- User-Agent hashes;
- raw referrers;
- query strings;
- raw user messages in metrics;
- per-user chat usage.

Logs and metrics should avoid personal data, secret values and raw visitor
messages.

## Metrics endpoint boundary

`/internal/metrics` is not a public product endpoint. It must be disabled by
default and protected with a bearer token when enabled.

Production tokens must be stored only in environment variables or the hosting
provider's secret store. They must not be committed to GitHub, dashboard JSON,
README files or documentation.

## Reuse disclaimer

The code is reusable under the project license, but personal profile content,
resume content, SEO metadata, screenshots, public CV files, video IDs and RAG
knowledge examples are template data. Replace them before reusing the project for
another person or company.
