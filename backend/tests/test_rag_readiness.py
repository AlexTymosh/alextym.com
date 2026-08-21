from app.rag.errors import RagCollectionContractError
from app.rag.readiness import RagReadinessProbe


def test_readiness_probe_caches_success_until_ttl_expires() -> None:
    calls = 0
    current_time = [100.0]

    def checker() -> None:
        nonlocal calls
        calls += 1

    probe = RagReadinessProbe(
        checker,
        ttl_seconds=60,
        clock=lambda: current_time[0],
    )

    assert probe.check().status == "ready"
    assert probe.check().status == "ready"
    assert calls == 1

    current_time[0] = 160.0

    assert probe.check().status == "ready"
    assert calls == 2


def test_readiness_probe_returns_bounded_contract_error() -> None:
    def checker() -> None:
        raise RagCollectionContractError(
            "Internal contract detail.",
            code="payload_index_missing",
        )

    result = RagReadinessProbe(checker, ttl_seconds=60).check()

    assert result.status == "not_ready"
    assert result.error_code == "payload_index_missing"
