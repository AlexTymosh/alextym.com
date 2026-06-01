from pathlib import Path


def test_named_vector_ingestion_script_has_module_entrypoint() -> None:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "ingest_generated_resume_chunks.py"
    )
    source = script_path.read_text(encoding="utf-8")

    assert 'if __name__ == "__main__":' in source
    assert "main()" in source.split('if __name__ == "__main__":', 1)[1]
