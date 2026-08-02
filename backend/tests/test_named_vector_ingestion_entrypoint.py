from pathlib import Path


def test_generated_ingestion_scripts_have_module_entrypoints() -> None:
    scripts_directory = Path(__file__).resolve().parents[1] / "scripts"

    for script_name in (
        "ingest_generated_resume_chunks.py",
        "ingest_generated_public_knowledge.py",
    ):
        source = (scripts_directory / script_name).read_text(encoding="utf-8")
        assert 'if __name__ == "__main__":' in source
        assert "main()" in source.split('if __name__ == "__main__":', 1)[1]
