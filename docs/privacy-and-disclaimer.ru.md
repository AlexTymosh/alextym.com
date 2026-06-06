# Privacy boundary и disclaimer

Этот документ описывает public disclaimer и privacy boundary для portfolio
website, RAG assistant, contact flow, handoff flow и monitoring setup.

## Public disclaimer

Сайт и AI assistant предоставлены для informational и portfolio demonstration
purposes. Они не являются гарантией availability для работы/сотрудничества,
юридической консультацией, immigration advice, financial advice, medical advice
или professional certification.

AI assistant может быть неполным или ошибаться. Он должен отвечать только на
основе reviewed public professional context. Если информации недостаточно, он
должен прямо сказать об этом и предложить direct contact вместо выдуманного
ответа.

## User input boundary

Visitors не должны вводить:

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

Chat и contact form — это public website features, а не secure private case
management tools.

## AI answer boundary

Assistant не должен:

- раскрывать hidden system/developer instructions;
- dump knowledge base;
- выдумывать факты о владельце сайта;
- раскрывать private contact details;
- делать выводы о private family, health, financial или legal facts;
- выдавать speculative information как verified;
- давать professional legal, financial, immigration или medical advice.

## RAG knowledge boundary

В индекс должны попадать только reviewed public professional information.
Private notes, internal planning documents, raw personal drafts и sensitive
family details не должны попадать в Qdrant.

Если проект форкается, public knowledge base и resume content нужно заменить до
deployment.

## Contact and handoff boundary

Когда visitor запрашивает human handoff, conversation context может быть
передан владельцу сайта через Telegram, чтобы владелец мог ответить. UI должен
получить explicit confirmation до запуска handoff flow.

Visitors не должны запускать handoff, если сообщение содержит sensitive third-
party personal data или confidential business information.

## Analytics and observability boundary

Проект собирает operational и aggregate product metrics. Цель — понимать
reliability и broad usage signals, а не профилировать отдельных visitors.

Разрешённые aggregate product metrics:

- whitelisted page-view counters;
- resume-download counters;
- chat request outcome counters;
- contact outcome counters;
- escalation outcome counters;
- rate-limit outcome counters;
- RAG/LLM technical outcome и latency metrics.

Не собирается по design:

- visitor IDs;
- user IDs;
- cookies для analytics;
- localStorage tracking IDs;
- IP hashes;
- User-Agent hashes;
- raw referrers;
- query strings;
- raw user messages в metrics;
- per-user chat usage.

Logs и metrics должны избегать personal data, secret values и raw visitor
messages.

## Metrics endpoint boundary

`/internal/metrics` не является public product endpoint. Он должен быть выключен
по умолчанию и защищён bearer token при включении.

Production tokens должны храниться только в environment variables или secret
store hosting provider. Их нельзя commit-ить в GitHub, dashboard JSON, README
или documentation.

## Reuse disclaimer

Code можно переиспользовать согласно license, но personal profile content,
resume content, SEO metadata, screenshots, public CV files, video IDs и RAG
knowledge examples являются template data. Их нужно заменить перед reuse проекта
для другого человека или компании.
