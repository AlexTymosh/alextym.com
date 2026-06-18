from pathlib import Path

from app.core.project_config import get_project_config


def get_public_resume_source_file() -> str:
    return get_project_config().content.public_resume_path


def get_public_resume_source_path(resume_source_path: Path | None = None) -> Path:
    if resume_source_path is None:
        return _resolve_repo_relative_path(Path(get_public_resume_source_file()))
    if resume_source_path.is_dir():
        return resume_source_path / "resume.md"
    return resume_source_path


def get_public_resume_source_file_for_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repository_root()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_repo_relative_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return _repository_root() / path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]
