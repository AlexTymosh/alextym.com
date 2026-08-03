from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.rag.case_study_contract import (
    CaseStudyCollection,
    CaseStudyMetadata,
    DOCUMENTATION_FILE_NAMES,
    REQUIRED_LEVEL_TWO_SECTIONS,
    RETRIEVAL_LEVEL_THREE_SECTIONS,
    discover_case_study_files,
    load_case_study_collection,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_STUDIES_DIRECTORY = REPOSITORY_ROOT / "content" / "public" / "case-studies"
RESUME_PATH = REPOSITORY_ROOT / "content" / "public" / "resume.md"
TEMPLATE_PATH = CASE_STUDIES_DIRECTORY / "CASE_STUDY_TEMPLATE.md"

EXPECTED_CASE_IDS = frozenset(
    {
        "case-corporate-borrower-credit-risk-process-analysis",
        "case-cross-border-skills-verification",
        "case-end-to-end-international-employment-service",
        "case-iot-buoy-fault-diagnosis",
        "case-kaizen-service-delivery-transformation",
        "case-payment-reconciliation-back-office",
        "case-pricing-data-erp-governance",
        "case-procurement-order-control",
        "case-recruitment-document-automation",
        "case-weee-reporting-automation",
    }
)
REMOVED_METADATA_FIELDS = frozenset(
    {
        "website",
        "visibility",
        "evidenceStatus",
        "sourceConfidence",
        "startDate",
        "endDate",
        "parentExperienceId",
    }
)
MID_SENTENCE_OWNER_PATTERN = re.compile(r"\b(?:demonstrates|before) The Owner\b")


@pytest.fixture(scope="module")
def collection() -> CaseStudyCollection:
    return load_case_study_collection(
        CASE_STUDIES_DIRECTORY,
        RESUME_PATH,
        expected_case_ids=EXPECTED_CASE_IDS,
    )


def test_repository_case_study_collection_matches_contract(
    collection: CaseStudyCollection,
) -> None:
    assert len(collection.documents) == len(EXPECTED_CASE_IDS)
    assert {document.metadata.id for document in collection.documents} == EXPECTED_CASE_IDS


def test_discovery_excludes_documentation_files() -> None:
    discovered = discover_case_study_files(CASE_STUDIES_DIRECTORY)

    assert all(path.name not in DOCUMENTATION_FILE_NAMES for path in discovered)
    assert all(path.name.endswith(".case.md") for path in discovered)


def test_only_case_files_and_known_documentation_use_markdown_extension() -> None:
    unexpected = [
        path
        for path in CASE_STUDIES_DIRECTORY.rglob("*.md")
        if path.name not in DOCUMENTATION_FILE_NAMES and not path.name.endswith(".case.md")
    ]

    assert not unexpected


def test_case_study_template_reflects_production_contract() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    metadata_aliases = {
        field.alias or field_name for field_name, field in CaseStudyMetadata.model_fields.items()
    }

    for field in metadata_aliases:
        assert re.search(rf"^{re.escape(field)}:", template, re.MULTILINE), (
            f"Case-study template is missing metadata field: {field}"
        )
    for field in REMOVED_METADATA_FIELDS:
        assert not re.search(rf"^{re.escape(field)}:", template, re.MULTILINE), (
            f"Case-study template still contains removed metadata field: {field}"
        )
    for heading in REQUIRED_LEVEL_TWO_SECTIONS:
        assert f"## {heading}" in template
    for heading in RETRIEVAL_LEVEL_THREE_SECTIONS:
        assert f"### {heading}" in template
    assert "- case-study" in template


def test_case_studies_use_owner_wording_consistently(
    collection: CaseStudyCollection,
) -> None:
    invalid: list[str] = []
    for document in collection.documents:
        text = document.source_path.read_text(encoding="utf-8")
        match = MID_SENTENCE_OWNER_PATTERN.search(text)
        if match:
            invalid.append(f"{document.source_path}: {match.group(0)!r}")

    assert not invalid, "Use 'the Owner' inside a sentence: " + "; ".join(invalid)
