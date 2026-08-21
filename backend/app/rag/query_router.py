from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from app.core.project_config import get_project_config
from app.rag.collection_contract import CASE_STUDY_SOURCE_GROUP, RESUME_SOURCE_GROUP
from app.rag.models import RetrievalFilter

_OWNER_REFERENCE = get_project_config().assistant.owner_reference.casefold()
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)

QueryIntent = Literal[
    "hard_skills",
    "soft_skills",
    "strengths",
    "services",
    "projects",
    "availability",
    "right_to_work",
    "experience",
    "education",
    "contact",
    "public_boundary",
    "out_of_scope",
    "general_profile",
]
SourceScope = Literal["all", "resume", "case_studies"]
CaseSectionIntent = Literal[
    "problem",
    "analysis",
    "implementation",
    "validation",
    "results",
    "limitations",
]


@dataclass(frozen=True)
class QueryRoute:
    intent: QueryIntent
    topic_hints: tuple[str, ...] = ()
    tag_hints: tuple[str, ...] = ()
    section_hints: tuple[str, ...] = ()
    source_scope: SourceScope = "all"
    case_section_hints: tuple[CaseSectionIntent, ...] = ()
    select_single_case: bool = False
    should_offer_handoff: bool = False

    def retrieval_text(self, query: str) -> str:
        hints = [*self.topic_hints, *self.tag_hints, *self.section_hints]
        if not hints:
            return query

        return " ".join([query, "retrieval hints:", *hints])

    def payload_filter(self) -> RetrievalFilter | None:
        if self.source_scope == "all":
            return None
        return RetrievalFilter(
            source_group_any=(
                (RESUME_SOURCE_GROUP,)
                if self.source_scope == "resume"
                else (CASE_STUDY_SOURCE_GROUP,)
            ),
        )


ROUTING_RULES: tuple[tuple[QueryIntent, tuple[str, ...], QueryRoute], ...] = (
    (
        "right_to_work",
        (
            "right to work",
            "work authorisation",
            "work authorization",
            "share code",
            "uk work",
            "work permit",
            "visa",
            "employment eligibility",
            "eligible to work",
        ),
        QueryRoute(
            intent="right_to_work",
            topic_hints=("right-to-work-uk-location",),
            tag_hints=(
                "right-to-work",
                "work-authorisation",
                "share-code",
                "uk-location",
                "employment-eligibility",
            ),
            section_hints=("experience",),
            should_offer_handoff=True,
        ),
    ),
    (
        "availability",
        (
            "availability",
            "available",
            "start date",
            "start a new job",
            "notice period",
            "interview scheduling",
            "when can",
            "when could",
            "calendar",
        ),
        QueryRoute(
            intent="availability",
            topic_hints=("availability-start-date",),
            tag_hints=("availability", "start-date", "hiring", "contact"),
            section_hints=("experience",),
            should_offer_handoff=True,
        ),
    ),
    (
        "public_boundary",
        (
            "weakness",
            "weaknesses",
            "weak point",
            "weak points",
            "development area",
            "development areas",
            "areas to improve",
            "professional limitations",
            "personal limitations",
            "his limitations",
            "her limitations",
            "your limitations",
            f"{_OWNER_REFERENCE}'s limitations",
            "site owner limitations",
            "site owner's limitations",
        ),
        QueryRoute(
            intent="public_boundary",
            topic_hints=("public-boundary-development-areas",),
            tag_hints=("public-boundary", "development-areas", "contact"),
            section_hints=("public-boundary-development-areas",),
            source_scope="resume",
            should_offer_handoff=True,
        ),
    ),
    (
        "services",
        (
            "what services",
            "which services",
            "services does",
            "services do",
            "services can",
            "offer services",
            "offers services",
            "software service",
            "software services",
            "build a website",
            "create a website",
            "make a website",
            "need a website",
            "build a web app",
            "create a web app",
            "need a web app",
            "internal tool",
            "business automation",
            "automation project",
            "api integration",
            "integrate api",
            "rag chatbot",
            "build software",
            "build an app",
            "create an app",
        ),
        QueryRoute(
            intent="services",
            topic_hints=(
                "software-services-and-collaboration",
                "typical-project-types",
                "service-fit-and-boundaries",
            ),
            tag_hints=(
                "services",
                "software-services",
                "website",
                "automation",
                "api",
                "rag",
                "chatbot",
                "internal-tools",
                "collaboration",
            ),
            section_hints=(
                "software services and collaboration",
                "typical project types",
                "service fit and boundaries",
            ),
            source_scope="resume",
            should_offer_handoff=True,
        ),
    ),
    (
        "strengths",
        (
            "strength",
            "strengths",
            "strong side",
            "strong sides",
            "advantage",
            "different",
            "why hire",
            "why should",
            "best at",
            "stands out",
            "what makes",
        ),
        QueryRoute(
            intent="strengths",
            topic_hints=("professional-strengths", "working-style"),
            tag_hints=(
                "strengths",
                "working-style",
                "automation-first",
                "business-processes",
                "analytical-thinking",
                "collaboration",
            ),
            section_hints=("professional strengths", "working style"),
        ),
    ),
    (
        "soft_skills",
        (
            "soft skill",
            "soft skills",
            "working style",
            "communication",
            "collaboration",
            "team player",
            "adaptable",
            "feedback",
            "problem solver",
            "problem-solving",
        ),
        QueryRoute(
            intent="soft_skills",
            topic_hints=("soft-skills-working-style",),
            tag_hints=(
                "soft-skills",
                "working-style",
                "communication",
                "adaptability",
                "problem-solving",
            ),
            section_hints=("experience", "working style"),
        ),
    ),
    (
        "hard_skills",
        (
            "hard skill",
            "hard skills",
            "technical skill",
            "technical skills",
            "tech stack",
            "stack",
            "tools",
            "python",
            "fastapi",
            "sql",
            "postgresql",
            "redis",
            "docker",
            "pytest",
            "api integration",
        ),
        QueryRoute(
            intent="hard_skills",
            topic_hints=("hard-skills",),
            tag_hints=(
                "hard-skills",
                "python",
                "fastapi",
                "api",
                "automation",
                "sql",
            ),
            section_hints=("experience",),
        ),
    ),
    (
        "projects",
        (
            "project",
            "projects",
            "portfolio project",
            "rag project",
            "website project",
            "saas project",
            "gdpr-aware",
            "gdpr",
            "qdrant",
            "ai assistant",
            "portfolio website",
        ),
        QueryRoute(
            intent="projects",
            topic_hints=(
                "project-ai-portfolio-rag-chat",
                "project-gdpr-aware-saas-automation-platform",
            ),
            tag_hints=("project", "rag", "qdrant", "fastapi", "saas", "gdpr"),
            section_hints=("experience",),
        ),
    ),
    (
        "education",
        (
            "education",
            "degree",
            "master",
            "bachelor",
            "university",
            "training",
            "course",
            "certificate",
            "certification",
            "coursera",
        ),
        QueryRoute(
            intent="education",
            tag_hints=("education", "training", "finance", "fastapi", "python"),
            section_hints=("education", "training"),
        ),
    ),
    (
        "experience",
        (
            "experience",
            "work experience",
            "worked",
            "career",
            "background",
            "hydrosphere",
            "dobra praca",
            "odoo",
            "erp",
            "crm",
            "excel",
            "vba",
            "dashboards",
            "reporting",
        ),
        QueryRoute(
            intent="experience",
            tag_hints=(
                "experience",
                "automation",
                "erp",
                "api",
                "excel",
                "reporting",
                "dashboards",
            ),
            section_hints=("experience",),
        ),
    ),
    (
        "contact",
        (
            "contact",
            "connect",
            "speak with",
            "talk to",
            "talk with",
            "hire",
            "offer",
            f"message {_OWNER_REFERENCE}",
        ),
        QueryRoute(
            intent="contact",
            tag_hints=("contact", "hiring", "recruiter"),
            should_offer_handoff=True,
        ),
    ),
)

OUT_OF_SCOPE_TERMS = (
    "how do i take pills",
    "nearest tube",
    "weather",
    "recipe",
    "bitcoin price",
    "elon musk",
)

CASE_STUDY_PATTERNS = (
    "case study",
    "case studies",
    "case example",
    "case examples",
    "a case study",
    "one case study",
    "tell me about one case",
    "give an example",
    "give me an example",
    "give example",
    "give me example",
    "give examples",
    "give me examples",
    "show an example",
    "show me an example",
    "show example",
    "show me example",
    "show examples",
    "show me examples",
    "provide an example",
    "tell me an example",
    "one example",
    "single example",
    "specific example",
    "concrete example",
    "an example of",
    "give me any case",
    "show me any case",
    "example where",
    "how did",
    "what limitations applied",
)
PLURAL_CASE_STUDY_PATTERNS = (
    "examples",
    "case studies",
    "case examples",
    "several cases",
    "multiple cases",
)
CASE_SECTION_RULES: tuple[
    tuple[CaseSectionIntent, tuple[str, ...]],
    ...,
] = (
    (
        "limitations",
        (
            "limitation",
            "limitations",
            "constraint",
            "constraints",
            "rejected",
            "too low",
            "low roi",
            "roi",
        ),
    ),
    (
        "validation",
        (
            "verify",
            "verified",
            "verification",
            "validate",
            "validated",
            "validation",
            "testing",
            "quality assurance",
        ),
    ),
    (
        "analysis",
        (
            "analysis",
            "analyse",
            "analysed",
            "analyze",
            "analyzed",
            "diagnosis",
            "diagnose",
            "distinguish",
            "telemetry",
            "bpmn",
            "investigate",
            "investigation",
            "assess",
            "assessment",
        ),
    ),
    (
        "implementation",
        (
            "automate",
            "automated",
            "automation",
            "implement",
            "implemented",
            "implementation",
            "design",
            "designed",
            "build",
            "built",
            "create",
            "created",
            "workflow",
            "integration",
            "integrate",
            "coordinated",
        ),
    ),
    (
        "results",
        (
            "result",
            "results",
            "outcome",
            "outcomes",
            "impact",
            "reduce",
            "reduced",
            "improve",
            "improved",
            "transform",
            "transformed",
            "benefit",
            "benefits",
            "achieved",
        ),
    ),
    (
        "problem",
        (
            "problem",
            "problems",
            "challenge",
            "challenges",
            "bottleneck",
            "bottlenecks",
            "error",
            "errors",
        ),
    ),
)


def route_query(query: str) -> QueryRoute:
    normalized_query = _normalize(query)
    if not normalized_query:
        return QueryRoute(intent="out_of_scope")

    if _contains_any(normalized_query, OUT_OF_SCOPE_TERMS):
        return QueryRoute(intent="out_of_scope")

    for _intent, triggers, route in ROUTING_RULES:
        if _contains_any(normalized_query, triggers):
            return _enrich_route(normalized_query, route)

    return _enrich_route(
        normalized_query,
        QueryRoute(
            intent="general_profile",
            tag_hints=("profile", "summary", "experience", "skills"),
        ),
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, term) for term in terms)


def _contains_phrase(text: str, phrase: str) -> bool:
    text_tokens = text.split()
    phrase_tokens = _normalize(phrase).split()
    if not phrase_tokens or len(phrase_tokens) > len(text_tokens):
        return False
    width = len(phrase_tokens)
    return any(
        text_tokens[index : index + width] == phrase_tokens
        for index in range(len(text_tokens) - width + 1)
    )


def _enrich_route(normalized_query: str, route: QueryRoute) -> QueryRoute:
    case_sections = tuple(
        section
        for section, triggers in CASE_SECTION_RULES
        if _contains_any(normalized_query, triggers)
    )
    if not _contains_any(normalized_query, CASE_STUDY_PATTERNS):
        return replace(route, case_section_hints=case_sections)

    return replace(
        route,
        source_scope="case_studies",
        case_section_hints=case_sections,
        select_single_case=not _contains_any(
            normalized_query,
            PLURAL_CASE_STUDY_PATTERNS,
        ),
    )


def _normalize(value: str) -> str:
    return " ".join(_TOKEN_PATTERN.findall(value.casefold()))
