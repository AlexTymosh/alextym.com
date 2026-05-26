import os
from pathlib import Path

from app.core.config import _load_env_file, _local_env_candidates


def test_load_env_file_sets_missing_values_without_overriding_existing_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'OPENAI_API_KEY="test-key"',
                "QDRANT_COLLECTION=alex_public_knowledge",
                "EXISTING_VALUE=from-file",
                "# COMMENTED=value",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    monkeypatch.delenv("COMMENTED", raising=False)
    monkeypatch.setenv("EXISTING_VALUE", "from-env")

    _load_env_file(env_file)

    assert os.environ["OPENAI_API_KEY"] == "test-key"
    assert os.environ["QDRANT_COLLECTION"] == "alex_public_knowledge"
    assert os.environ["EXISTING_VALUE"] == "from-env"
    assert "COMMENTED" not in os.environ


def test_local_env_candidates_include_current_backend_env(monkeypatch, tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    monkeypatch.chdir(backend_dir)

    candidates = _local_env_candidates()

    assert candidates[0] == backend_dir / ".env"
    assert candidates[1] == backend_dir / "backend" / ".env"
