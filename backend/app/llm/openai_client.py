from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from app.core.config import Settings
from app.llm.client import ProviderConfigurationError, ProviderRequestError
from app.rag.prompt_builder import PromptBundle


class OpenAIEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ProviderConfigurationError("OpenAI API key is not configured.")
        if not model:
            raise ProviderConfigurationError("OpenAI embedding model is not configured.")
        if dimensions <= 0:
            raise ProviderConfigurationError("OpenAI embedding dimensions must be positive.")

        self._client = client or OpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIEmbeddingClient":
        return cls(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized_texts = [text.strip() for text in texts if text.strip()]
        if not normalized_texts:
            return []

        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=normalized_texts,
                dimensions=self._dimensions,
            )
        except Exception as exc:
            raise ProviderRequestError("OpenAI embedding request failed.") from exc

        embeddings = [list(item.embedding) for item in response.data]
        if len(embeddings) != len(normalized_texts):
            raise ProviderRequestError("OpenAI embedding response size mismatch.")
        return embeddings

    def embed_text(self, text: str) -> list[float]:
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        reasoning_effort: str,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ProviderConfigurationError("OpenAI API key is not configured.")
        if not model:
            raise ProviderConfigurationError("OpenAI model is not configured.")
        if max_output_tokens <= 0:
            raise ProviderConfigurationError("OpenAI max output tokens must be positive.")

        self._client = client or OpenAI(api_key=api_key)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort.strip().lower()

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIResponsesClient":
        return cls(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_output_tokens=settings.openai_max_output_tokens,
            reasoning_effort=settings.openai_reasoning_effort,
        )

    def answer(self, prompt: PromptBundle) -> str:
        try:
            response = self._client.responses.create(**self._request_options(prompt))
        except Exception as exc:
            raise ProviderRequestError("OpenAI response request failed.") from exc

        answer = _extract_response_text(response)
        if not answer:
            raise ProviderRequestError("OpenAI response did not contain text.")
        return answer

    def stream_answer(self, prompt: PromptBundle) -> Iterator[str]:
        request_options = self._request_options(prompt)
        request_options["stream"] = True

        try:
            stream = self._client.responses.create(**request_options)
        except Exception as exc:
            raise ProviderRequestError("OpenAI streaming request failed.") from exc

        try:
            for event in stream:
                delta = _extract_stream_delta(event)
                if delta:
                    yield delta
        except Exception as exc:
            raise ProviderRequestError("OpenAI streaming response failed.") from exc

    def _request_options(self, prompt: PromptBundle) -> dict[str, Any]:
        request_options: dict[str, Any] = {
            "model": self._model,
            "input": prompt.as_messages(),
            "max_output_tokens": self._max_output_tokens,
        }
        if self._reasoning_effort and self._reasoning_effort != "disabled":
            request_options["reasoning"] = {"effort": self._reasoning_effort}
        return request_options


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    fragments: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            text = getattr(content_item, "text", None)
            if isinstance(text, str):
                fragments.append(text)

    return "".join(fragments).strip()


def _extract_stream_delta(event: Any) -> str:
    event_type = _event_value(event, "type")
    if event_type not in {"response.output_text.delta", "response.refusal.delta"}:
        return ""

    delta = _event_value(event, "delta")
    return delta if isinstance(delta, str) else ""


def _event_value(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)
