from typing import Literal

DenseVectorName = Literal["title_dense", "body_dense", "summary_dense"]

NAMED_DENSE_VECTOR_NAMES: tuple[DenseVectorName, ...] = (
    "title_dense",
    "body_dense",
    "summary_dense",
)

DEFAULT_QUERY_VECTOR_NAME: DenseVectorName = "body_dense"

VectorMode = Literal["single", "named"]


def normalise_vector_mode(value: str) -> VectorMode:
    return "named" if value == "named" else "single"


def normalise_query_vector_name(value: str) -> DenseVectorName:
    if value in NAMED_DENSE_VECTOR_NAMES:
        return value
    return DEFAULT_QUERY_VECTOR_NAME
