import json
from urllib.parse import urlparse

from app.core.project_config import find_project_config_path, get_project_config


def test_project_config_loader_reads_shared_config() -> None:
    config_path = find_project_config_path()
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    config = get_project_config()

    assert config_path.as_posix().endswith("config/project.config.json")
    assert config.site.domain == urlparse(raw_config["site"]["canonicalUrl"]).netloc
    assert config.site.canonical_url == raw_config["site"]["canonicalUrl"]
    assert config.content.public_resume_path == raw_config["content"]["publicResumePath"]
    assert config.owner.short_name == raw_config["owner"]["shortName"]
    assert config.owner.russian_name == raw_config["owner"]["localizedNames"]["russian"]
    assert config.owner.ukrainian_name == raw_config["owner"]["localizedNames"]["ukrainian"]
    assert config.site.domain.strip()
    assert config.owner.short_name.strip()
    assert (
        config.assistant.display_name
        == f"{raw_config['owner']['possessiveName']} digital assistant"
    )
    assert config.assistant.owner_reference == raw_config["owner"]["shortName"]


def test_project_config_loader_exposes_backend_required_copy() -> None:
    config = get_project_config()
    required_values = [
        config.owner.display_name,
        config.owner.short_name,
        config.owner.possessive_name,
        config.owner.russian_name,
        config.owner.ukrainian_name,
        config.content.public_resume_path,
        config.site.domain,
        config.assistant.display_name,
        config.assistant.owner_reference,
    ]

    assert all(value.strip() for value in required_values)
    assert config.owner.public_aliases
    assert all(alias.strip() for alias in config.owner.public_aliases)


def test_project_config_loader_exposes_language_restrictions() -> None:
    raw_config = json.loads(find_project_config_path().read_text(encoding="utf-8"))
    config = get_project_config()

    raw_restrictions = raw_config["chat"]["languageRestrictions"]
    assert (
        config.chat.language_restrictions.russian.enabled is raw_restrictions["russian"]["enabled"]
    )
    assert (
        config.chat.language_restrictions.ukrainian.enabled
        is raw_restrictions["ukrainian"]["enabled"]
    )
    assert (
        config.chat.language_restrictions.other_non_english.enabled
        is raw_restrictions["otherNonEnglish"]["enabled"]
    )
