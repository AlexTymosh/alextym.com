from app.rag.context_formatter import RetrievedContextFormatter
from app.rag.models import ChunkMetadata, KnowledgeChunk


def test_formatter_uses_answer_facts_instead_of_raw_content() -> None:
    chunk = KnowledgeChunk(
        id="resume:hard-skills:rag",
        content="Raw chunk content that should not be sent to the LLM.",
        metadata=ChunkMetadata(
            source="Hard Skills",
            section="experience",
            topic="hard-skills",
            tags=("python", "fastapi"),
            extra={
                "answer_facts": [
                    "Alex uses Python for automation and backend work.",
                    "Alex uses FastAPI for API services.",
                ],
                "retrieval_hints": ["Do not send this to the LLM."],
                "vector_inputs": {"body_dense": "Do not send this either."},
            },
        ),
    )

    context = RetrievedContextFormatter().format([chunk])

    assert "Alex uses Python for automation and backend work." in context
    assert "Alex uses FastAPI for API services." in context
    assert "Raw chunk content" not in context
    assert "Do not send this to the LLM" not in context
    assert "Do not send this either" not in context


def test_formatter_falls_back_to_content_for_legacy_chunks() -> None:
    chunk = KnowledgeChunk(
        id="legacy",
        content="Legacy public knowledge content.",
        metadata=ChunkMetadata(
            source="resume.md",
            section="Summary",
            topic="summary",
        ),
    )

    context = RetrievedContextFormatter().format([chunk])

    assert "Legacy public knowledge content." in context
    assert "topic: summary" in context


def test_formatter_returns_empty_context_message_without_chunks() -> None:
    context = RetrievedContextFormatter().format([])

    assert context == "Public knowledge context: none."


def test_prompt_builder_uses_compressed_retrieved_context() -> None:
    from app.rag.prompt_builder import PromptBuilder

    chunk = KnowledgeChunk(
        id="resume:soft-skills:rag",
        content="Verbose content that should be compressed.",
        metadata=ChunkMetadata(
            source="Soft Skills",
            section="experience",
            topic="soft-skills-working-style",
            extra={"answer_facts": ["Alex communicates clearly."]},
        ),
    )

    messages = (
        PromptBuilder()
        .build(
            question="What are Alex's soft skills?",
            chunks=[chunk],
        )
        .as_messages()
    )

    assert "Alex communicates clearly." in messages[1]["content"]
    assert "Verbose content" not in messages[1]["content"]
