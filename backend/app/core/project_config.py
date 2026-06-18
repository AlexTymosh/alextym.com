from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONFIG_RELATIVE_PATH = Path("config") / "project.config.json"


class ProjectConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectContentConfig:
    public_resume_path: str


@dataclass(frozen=True)
class ProjectOwnerConfig:
    display_name: str
    short_name: str
    possessive_name: str
    russian_name: str
    ukrainian_name: str
    public_aliases: tuple[str, ...]


@dataclass(frozen=True)
class ProjectSiteConfig:
    name: str
    domain: str
    canonical_url: str


@dataclass(frozen=True)
class LanguageRestrictionConfig:
    enabled: bool


@dataclass(frozen=True)
class ChatLanguageRestrictionsConfig:
    russian: LanguageRestrictionConfig
    ukrainian: LanguageRestrictionConfig
    other_non_english: LanguageRestrictionConfig


@dataclass(frozen=True)
class ChatConfig:
    language_restrictions: ChatLanguageRestrictionsConfig


@dataclass(frozen=True)
class AssistantConfig:
    display_name: str
    owner_reference: str


@dataclass(frozen=True)
class ProjectConfig:
    content: ProjectContentConfig
    owner: ProjectOwnerConfig
    site: ProjectSiteConfig
    chat: ChatConfig
    assistant: AssistantConfig


@lru_cache
def get_project_config() -> ProjectConfig:
    config_path = find_project_config_path()
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProjectConfigError(f"Project config could not be read: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectConfigError(f"Project config is not valid JSON: {config_path}") from exc

    return _parse_project_config(raw_config)


def find_project_config_path() -> Path:
    for candidate in _project_config_candidates():
        if candidate.is_file():
            return candidate

    searched_paths = ", ".join(str(path) for path in _project_config_candidates())
    raise ProjectConfigError(f"Project config was not found. Searched: {searched_paths}")


def clear_project_config_cache() -> None:
    get_project_config.cache_clear()


def _project_config_candidates() -> tuple[Path, ...]:
    module_path = Path(__file__).resolve()
    candidates = [
        Path.cwd() / CONFIG_RELATIVE_PATH,
        Path.cwd().parent / CONFIG_RELATIVE_PATH,
        *(parent / CONFIG_RELATIVE_PATH for parent in module_path.parents),
    ]
    return _dedupe_paths(candidates)


def _dedupe_paths(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    unique_paths: list[Path] = []
    for path in paths:
        resolved = str(path.resolve(strict=False))
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)
    return tuple(unique_paths)


def _parse_project_config(raw_config: object) -> ProjectConfig:
    config = _as_mapping(raw_config, "project config")

    content = _required_mapping(config, "content")
    owner = _required_mapping(config, "owner")
    site = _required_mapping(config, "site")
    chat = _required_mapping(config, "chat")
    language_restrictions = _required_mapping(
        chat,
        "languageRestrictions",
        path="chat.languageRestrictions",
    )
    localized_names = _required_mapping(owner, "localizedNames", path="owner.localizedNames")
    owner_config = ProjectOwnerConfig(
        display_name=_required_string(owner, "displayName", path="owner.displayName"),
        short_name=_required_string(owner, "shortName", path="owner.shortName"),
        possessive_name=_required_string(
            owner,
            "possessiveName",
            path="owner.possessiveName",
        ),
        russian_name=_required_string(
            localized_names,
            "russian",
            path="owner.localizedNames.russian",
        ),
        ukrainian_name=_required_string(
            localized_names,
            "ukrainian",
            path="owner.localizedNames.ukrainian",
        ),
        public_aliases=_required_string_tuple(
            owner,
            "publicAliases",
            path="owner.publicAliases",
        ),
    )

    return ProjectConfig(
        content=ProjectContentConfig(
            public_resume_path=_required_string(
                content,
                "publicResumePath",
                path="content.publicResumePath",
            ),
        ),
        owner=owner_config,
        site=ProjectSiteConfig(
            name=_required_string(site, "name", path="site.name"),
            canonical_url=_required_string(site, "canonicalUrl", path="site.canonicalUrl"),
            domain=_domain_from_url(
                _required_string(site, "canonicalUrl", path="site.canonicalUrl")
            ),
        ),
        chat=ChatConfig(
            language_restrictions=ChatLanguageRestrictionsConfig(
                russian=_language_restriction(
                    language_restrictions,
                    "russian",
                    path="chat.languageRestrictions.russian",
                ),
                ukrainian=_language_restriction(
                    language_restrictions,
                    "ukrainian",
                    path="chat.languageRestrictions.ukrainian",
                ),
                other_non_english=_language_restriction(
                    language_restrictions,
                    "otherNonEnglish",
                    path="chat.languageRestrictions.otherNonEnglish",
                ),
            ),
        ),
        assistant=AssistantConfig(
            display_name=f"{owner_config.possessive_name} digital assistant",
            owner_reference=owner_config.short_name,
        ),
    )


def _language_restriction(
    source: Mapping[str, Any],
    key: str,
    *,
    path: str,
) -> LanguageRestrictionConfig:
    restriction = _required_mapping(source, key, path=path)
    return LanguageRestrictionConfig(
        enabled=_required_bool(restriction, "enabled", path=f"{path}.enabled"),
    )


def _required_mapping(
    source: Mapping[str, Any],
    key: str,
    *,
    path: str | None = None,
) -> Mapping[str, Any]:
    value = source.get(key)
    return _as_mapping(value, path or key)


def _as_mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectConfigError(f"{path} must be an object.")
    return value


def _required_string(source: Mapping[str, Any], key: str, *, path: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProjectConfigError(f"{path} must be a non-empty string.")
    return value


def _required_bool(source: Mapping[str, Any], key: str, *, path: str) -> bool:
    value = source.get(key)
    if not isinstance(value, bool):
        raise ProjectConfigError(f"{path} must be a boolean.")
    return value


def _domain_from_url(value: str) -> str:
    parsed_url = urlparse(value)
    if not parsed_url.netloc:
        raise ProjectConfigError("site.canonicalUrl must include a domain.")
    return parsed_url.netloc


def _required_string_tuple(
    source: Mapping[str, Any],
    key: str,
    *,
    path: str,
) -> tuple[str, ...]:
    value = source.get(key)
    if not isinstance(value, list) or not value:
        raise ProjectConfigError(f"{path} must be a non-empty string array.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ProjectConfigError(f"{path} must contain only non-empty strings.")
    return tuple(value)
