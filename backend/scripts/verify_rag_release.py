from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from prometheus_client.parser import text_string_to_metric_families

from app.core.config import Settings, get_settings
from app.rag.collection_contract import RagCollectionContract
from app.rag.errors import RetrievalError
from app.rag.factory import get_configured_retriever
from app.rag.models import KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore
from scripts.run_chat_evals import evaluate_response, load_eval_cases
from scripts.run_retrieval_evals import evaluate_case, load_retrieval_eval_cases

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANARIES_PATH = BACKEND_ROOT / "evals" / "rag_release_canaries.json"
RAG_ERROR_STAGES = {"collection_contract", "vector_search"}
PARITY_FIELDS = (
    "confidence",
    "not_enough_data",
    "retrieval_status",
    "handoff_suggested",
    "handoff_reason",
    "language_unsupported",
    "user_requested_human",
)


class ReleaseVerificationError(RuntimeError):
    pass


class RetrieverProtocol(Protocol):
    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]: ...


class CollectionStoreProtocol(Protocol):
    def validate_contract(self, contract: RagCollectionContract) -> None: ...


class ReleaseApiClientProtocol(Protocol):
    def readiness(self) -> dict[str, Any]: ...

    def chat_json(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def chat_stream(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ReleaseCanary:
    id: str
    retrieval_case: dict[str, Any]
    answer_case: dict[str, Any]
    expected_case_id: str
    expected_case_sections: tuple[str, ...]


def load_release_canaries(path: Path = DEFAULT_CANARIES_PATH) -> list[ReleaseCanary]:
    payload = _read_json_object(path, label="Release canary manifest")
    if payload.get("schema_version") != 1:
        raise ReleaseVerificationError("Release canary manifest schema_version must be 1.")

    retrieval_path = _manifest_path(path, payload.get("retrieval_cases"), "retrieval_cases")
    answer_path = _manifest_path(path, payload.get("answer_cases"), "answer_cases")
    retrieval_suite = _required_text(payload.get("retrieval_suite"), "retrieval_suite")
    answer_suite = _required_text(payload.get("answer_suite"), "answer_suite")
    retrieval_cases = {
        str(case["id"]): case
        for case in load_retrieval_eval_cases(retrieval_path, suite=retrieval_suite)
    }
    answer_cases = {
        str(case["id"]): case for case in load_eval_cases(answer_path, suite=answer_suite)
    }

    selections = payload.get("canaries")
    if not isinstance(selections, list) or not selections:
        raise ReleaseVerificationError("Release canary manifest must select canaries.")

    canaries = [
        _resolve_canary(selection, retrieval_cases=retrieval_cases, answer_cases=answer_cases)
        for selection in selections
    ]
    ids = [canary.id for canary in canaries]
    if len(ids) != len(set(ids)):
        raise ReleaseVerificationError("Release canary IDs must be unique.")
    return canaries


def verify_collection_contract(
    *,
    settings: Settings | None = None,
    store: CollectionStoreProtocol | None = None,
) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    if not resolved_settings.qdrant_url:
        raise ReleaseVerificationError("QDRANT_URL is required for the collection probe.")

    contract = RagCollectionContract.for_runtime(resolved_settings)
    resolved_store = store or QdrantKnowledgeStore.from_settings(resolved_settings)
    resolved_store.validate_contract(contract)
    return {
        "check": "collection_contract",
        "status": "passed",
        "collection": resolved_settings.qdrant_collection,
        "vector_mode": contract.vector_mode,
        "vector_size": contract.vector_size,
        "required_source_groups": list(contract.required_source_groups),
    }


def verify_retrieval_canaries(
    canaries: list[ReleaseCanary],
    *,
    retriever: RetrieverProtocol,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for canary in canaries:
        retrieval_case = canary.retrieval_case
        limit = retrieval_case.get("limit")
        resolved_limit = limit if isinstance(limit, int) and limit > 0 else 6
        chunks = retriever.retrieve(str(retrieval_case["query"]), limit=resolved_limit)
        result = evaluate_case(retrieval_case, chunks=list(chunks))
        if not result.passed:
            checks = sorted({failure.check for failure in result.failures})
            raise ReleaseVerificationError(
                f"Retrieval canary {canary.id!r} failed checks: {', '.join(checks)}."
            )
        results.append(
            {
                "id": canary.id,
                "status": "passed",
                "retrieved_chunks": len(result.retrieved),
                "case_id": canary.expected_case_id,
            }
        )
    return {"check": "retrieval_canaries", "status": "passed", "canaries": results}


def verify_deployed_api(
    canaries: list[ReleaseCanary],
    *,
    client: ReleaseApiClientProtocol,
) -> dict[str, object]:
    readiness = client.readiness()
    _verify_readiness(readiness)

    results: list[dict[str, object]] = []
    for canary in canaries:
        payload = {"message": canary.answer_case["message"], "history": []}
        json_response = client.chat_json(payload)
        stream_response = client.chat_stream(payload)
        _verify_api_response(canary, json_response, transport="json")
        _verify_api_response(canary, stream_response, transport="sse")
        if _parity_signature(json_response) != _parity_signature(stream_response):
            raise ReleaseVerificationError(
                f"Canary {canary.id!r} has different JSON and SSE response contracts."
            )
        results.append(
            {
                "id": canary.id,
                "status": "passed",
                "case_id": canary.expected_case_id,
                "transports": ["json", "sse"],
            }
        )
    return {"check": "deployed_api", "status": "passed", "canaries": results}


def parse_sse_chat_response(body: str) -> dict[str, Any]:
    answer_parts: list[str] = []
    sources: list[dict[str, Any]] | None = None
    done: dict[str, Any] | None = None
    for event, data in _parse_sse_events(body):
        payload = _parse_json_object(data, label=f"SSE {event} event")
        if event == "token":
            text = payload.get("text")
            if isinstance(text, str):
                answer_parts.append(text)
        elif event == "sources":
            raw_sources = payload.get("sources")
            if not isinstance(raw_sources, list):
                raise ReleaseVerificationError("SSE sources event must contain a list.")
            sources = [source for source in raw_sources if isinstance(source, dict)]
        elif event == "done":
            done = payload
        elif event == "error":
            raise ReleaseVerificationError("SSE canary returned an error event.")

    if sources is None or done is None:
        raise ReleaseVerificationError("SSE canary did not complete the chat contract.")
    return {"answer": "".join(answer_parts), "sources": sources, **done}


def verify_retrieval_error_metrics(
    metrics_text: str,
    *,
    max_errors: float = 0.0,
) -> dict[str, object]:
    error_count = 0.0
    retrieval_metric_seen = False
    for family in text_string_to_metric_families(metrics_text):
        for sample in family.samples:
            if sample.name != "portfolio_rag_retrievals_total":
                continue
            retrieval_metric_seen = True
            if sample.labels.get("outcome") != "error":
                continue
            if sample.labels.get("stage") not in RAG_ERROR_STAGES:
                continue
            error_count += float(sample.value)

    if not retrieval_metric_seen:
        raise ReleaseVerificationError(
            "RAG retrieval metrics are missing from the metrics endpoint."
        )
    if error_count > max_errors:
        raise ReleaseVerificationError("RAG retrieval error metrics exceed the release threshold.")
    return {
        "check": "retrieval_error_metrics",
        "status": "passed",
        "qdrant_error_count": error_count,
        "maximum": max_errors,
    }


class HttpReleaseClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 60.0) -> None:
        import httpx

        self._base_url = _normalise_base_url(base_url)
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "alextym-rag-release-verifier/1"},
        )

    def __enter__(self) -> "HttpReleaseClient":
        return self

    def __exit__(self, *args: object) -> None:
        self._client.close()

    def readiness(self) -> dict[str, Any]:
        response = self._client.get(self._url("/api/health/ready"))
        return self._json_response(response, path="/api/health/ready")

    def chat_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(self._url("/api/chat"), json=payload)
        return self._json_response(response, path="/api/chat")

    def chat_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            self._url("/api/chat/stream"),
            json=payload,
            headers={"Accept": "text/event-stream"},
        )
        self._require_success(response, path="/api/chat/stream")
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("text/event-stream"):
            raise ReleaseVerificationError("Chat stream did not return text/event-stream.")
        return parse_sse_chat_response(response.text)

    def metrics(self, *, path: str, token: str) -> str:
        response = self._client.get(
            self._url(_normalise_metrics_path(path)),
            headers={"Authorization": f"Bearer {token}"},
        )
        self._require_success(response, path=path)
        return response.text

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _json_response(self, response: Any, *, path: str) -> dict[str, Any]:
        self._require_success(response, path=path)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ReleaseVerificationError(f"{path} did not return JSON.") from exc
        if not isinstance(payload, dict):
            raise ReleaseVerificationError(f"{path} did not return a JSON object.")
        return payload

    @staticmethod
    def _require_success(response: Any, *, path: str) -> None:
        if response.status_code != 200:
            raise ReleaseVerificationError(f"{path} returned HTTP {response.status_code}.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = _run_command(args)
        _write_report(args.report_json, report)
        print(f"RAG release check passed: {report['check']}")
        return 0
    except RetrievalError as exc:
        print(
            f"RAG release check failed: {exc.stage}/{exc.code}.",
            file=sys.stderr,
        )
    except ReleaseVerificationError as exc:
        print(f"RAG release check failed: {exc}", file=sys.stderr)
    except Exception as exc:
        print(
            f"RAG release check failed with unexpected {type(exc).__name__}.",
            file=sys.stderr,
        )
    return 1


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "collection":
        return verify_collection_contract()
    if args.command == "retrieval":
        settings = get_settings()
        if not settings.openai_api_key or not settings.qdrant_url:
            raise ReleaseVerificationError(
                "OPENAI_API_KEY and QDRANT_URL are required for retrieval canaries."
            )
        return verify_retrieval_canaries(
            load_release_canaries(args.manifest),
            retriever=get_configured_retriever(settings),
        )
    if args.command == "api":
        with HttpReleaseClient(args.base_url, timeout_seconds=args.timeout) as client:
            return verify_deployed_api(load_release_canaries(args.manifest), client=client)
    if args.command == "metrics":
        token = os.getenv(args.token_env, "")
        if not token:
            raise ReleaseVerificationError(f"{args.token_env} is required for metrics check.")
        with HttpReleaseClient(args.base_url, timeout_seconds=args.timeout) as client:
            metrics_text = client.metrics(path=args.metrics_path, token=token)
        return verify_retrieval_error_metrics(metrics_text, max_errors=args.max_errors)
    raise ReleaseVerificationError("Unknown release verification command.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run read-only RAG release verification.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collection = subparsers.add_parser("collection", help="Validate the Qdrant contract.")
    _add_report_argument(collection)

    retrieval = subparsers.add_parser("retrieval", help="Run direct retrieval canaries.")
    _add_manifest_argument(retrieval)
    _add_report_argument(retrieval)

    api = subparsers.add_parser("api", help="Run deployed JSON/SSE canaries.")
    _add_manifest_argument(api)
    _add_http_arguments(api)
    _add_report_argument(api)

    metrics = subparsers.add_parser("metrics", help="Check deployed RAG error metrics.")
    _add_http_arguments(metrics)
    metrics.add_argument("--metrics-path", default="/internal/metrics")
    metrics.add_argument("--token-env", default="METRICS_TOKEN")
    metrics.add_argument("--max-errors", type=float, default=0.0)
    _add_report_argument(metrics)
    return parser


def _add_manifest_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CANARIES_PATH)


def _add_http_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)


def _add_report_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--report-json", type=Path)


def _resolve_canary(
    selection: object,
    *,
    retrieval_cases: dict[str, dict[str, Any]],
    answer_cases: dict[str, dict[str, Any]],
) -> ReleaseCanary:
    if not isinstance(selection, dict):
        raise ReleaseVerificationError("Release canary selection must be an object.")
    canary_id = _required_text(selection.get("id"), "canary.id")
    retrieval_id = _required_text(selection.get("retrieval_case_id"), "canary.retrieval_case_id")
    answer_id = _required_text(selection.get("answer_case_id"), "canary.answer_case_id")
    if retrieval_id not in retrieval_cases or answer_id not in answer_cases:
        raise ReleaseVerificationError(f"Canary {canary_id!r} references an unknown eval case.")

    retrieval_case = retrieval_cases[retrieval_id]
    answer_case = answer_cases[answer_id]
    if retrieval_case.get("query") != answer_case.get("message"):
        raise ReleaseVerificationError(f"Canary {canary_id!r} eval questions do not match.")
    retrieval_case_id = _required_text(retrieval_case.get("case_id"), "retrieval case_id")
    answer_case_id = _required_text(answer_case.get("case_id"), "answer case_id")
    if retrieval_case_id != answer_case_id:
        raise ReleaseVerificationError(f"Canary {canary_id!r} eval case IDs do not match.")

    expected = retrieval_case.get("expected")
    if not isinstance(expected, dict):
        raise ReleaseVerificationError(f"Canary {canary_id!r} retrieval expectations are invalid.")
    sections = _string_tuple(expected.get("must_include_case_section_any"))
    if not sections:
        raise ReleaseVerificationError(f"Canary {canary_id!r} has no case-section expectation.")
    return ReleaseCanary(
        id=canary_id,
        retrieval_case=retrieval_case,
        answer_case=answer_case,
        expected_case_id=retrieval_case_id,
        expected_case_sections=sections,
    )


def _verify_readiness(payload: dict[str, Any]) -> None:
    if (
        payload.get("status") != "ready"
        or payload.get("vector_db") != "ready"
        or payload.get("llm_config") != "configured"
    ):
        raise ReleaseVerificationError("Deployed backend is not ready for RAG canaries.")


def _verify_api_response(
    canary: ReleaseCanary,
    response: dict[str, Any],
    *,
    transport: str,
) -> None:
    answer = response.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ReleaseVerificationError(
            f"Canary {canary.id!r} returned an empty {transport} answer."
        )

    eval_case = dict(canary.answer_case)
    expected = dict(canary.answer_case.get("expected") or {})
    expected["must_include_source_case_id_any"] = [canary.expected_case_id]
    expected["must_include_source_case_section_any"] = list(canary.expected_case_sections)
    eval_case["expected"] = expected
    result = evaluate_response(eval_case, response)
    if not result.passed:
        checks = sorted({failure.check for failure in result.failures})
        raise ReleaseVerificationError(
            f"Canary {canary.id!r} failed {transport} checks: {', '.join(checks)}."
        )


def _parity_signature(response: dict[str, Any]) -> tuple[object, ...]:
    sources = response.get("sources")
    source_signature = tuple(
        sorted(
            (
                str(source.get("title") or ""),
                str(source.get("section") or ""),
                str(source.get("confidence") or ""),
                str(source.get("case_id") or ""),
                str(source.get("case_section") or ""),
            )
            for source in sources or []
            if isinstance(source, dict)
        )
    )
    return (source_signature, *(response.get(field) for field in PARITY_FIELDS))


def _parse_sse_events(body: str) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    event_name = "message"
    data_lines: list[str] = []
    for line in [*body.splitlines(), ""]:
        if not line:
            if data_lines:
                events.append((event_name, "\n".join(data_lines)))
            event_name = "message"
            data_lines = []
        elif line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())
    return events


def _manifest_path(manifest: Path, value: object, field: str) -> Path:
    relative_path = Path(_required_text(value, field))
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ReleaseVerificationError(f"{field} must be relative to the manifest.")
    return manifest.parent / relative_path


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"{label} could not be loaded.") from exc
    if not isinstance(payload, dict):
        raise ReleaseVerificationError(f"{label} must be a JSON object.")
    return payload


def _parse_json_object(value: str, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ReleaseVerificationError(f"{label} contains invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise ReleaseVerificationError(f"{label} must contain a JSON object.")
    return payload


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseVerificationError(f"{field} must be a non-empty string.")
    return value.strip()


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _normalise_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ReleaseVerificationError("base-url must be an HTTP(S) origin without credentials.")
    return f"{parsed.scheme}://{parsed.netloc}"


def _normalise_metrics_path(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("/") or "?" in stripped or "#" in stripped:
        raise ReleaseVerificationError("metrics-path must be an absolute URL path.")
    return stripped


def _write_report(path: Path | None, report: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
