from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QueryIntent = Literal[
    "hard_skills",
    "soft_skills",
    "projects",
    "availability",
    "right_to_work",
    "experience",
    "education",
    "contact",
    "out_of_scope",
    "general_profile",
]


@dataclass(frozen=True)
class QueryRoute:
    intent: QueryIntent
    topic_hints: tuple[str, ...] = ()
    tag_hints: tuple[str, ...] = ()
    section_hints: tuple[str, ...] = ()
    should_offer_handoff: bool = False

    def retrieval_text(self, query: str) -> str:
        hints = [*self.topic_hints, *self.tag_hints, *self.section_hints]
        if not hints:
            return query

        return " ".join([query, "retrieval hints:", *hints])


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
            section_hints=("experience",),
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
            "message alex",
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


def route_query(query: str) -> QueryRoute:
    normalized_query = _normalize(query)
    if not normalized_query:
        return QueryRoute(intent="out_of_scope")

    if _contains_any(normalized_query, OUT_OF_SCOPE_TERMS):
        return QueryRoute(intent="out_of_scope")

    for _intent, triggers, route in ROUTING_RULES:
        if _contains_any(normalized_query, triggers):
            return route

    return QueryRoute(
        intent="general_profile",
        tag_hints=("profile", "summary", "experience", "skills"),
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("/", " ").replace("-", " ").split())
