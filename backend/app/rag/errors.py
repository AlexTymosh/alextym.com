from typing import Literal

from app.llm.client import ProviderRequestError

RetrievalStage = Literal["embedding", "vector_search", "collection_contract"]


class RetrievalError(ProviderRequestError):
    def __init__(
        self,
        message: str,
        *,
        stage: RetrievalStage,
        code: str,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.retryable = retryable


class RagCollectionContractError(RetrievalError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(
            message,
            stage="collection_contract",
            code=code,
            retryable=False,
        )
