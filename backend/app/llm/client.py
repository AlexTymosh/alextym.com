from typing import Protocol

from app.rag.prompt_builder import PromptBundle


class ProviderConfigurationError(RuntimeError):
    """Raised when an external provider is not configured."""


class ProviderRequestError(RuntimeError):
    """Raised when an external provider request fails."""


class EmbeddingClient(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text inputs."""

    def embed_text(self, text: str) -> list[float]:
        """Embed one text input."""


class LLMClient(Protocol):
    def answer(self, prompt: PromptBundle) -> str:
        """Generate a final answer from a grounded prompt."""
