"""Offline tests: no Firebase, network, credentials or real clock required."""

from preferans.online.quota_guard import QuotaCircuit, QuotaUnavailable, is_quota_error
import pytest


class ResourceExhausted(Exception):
    pass


def test_circuit_is_bounded_and_no_concurrent_extension():
    at = [100.0]
    circuit = QuotaCircuit(lambda: at[0])
    circuit.require_available()
    assert not circuit.record_failure(PermissionError())
    assert circuit.record_failure(ResourceExhausted())
    assert circuit.retry_after() == 120
    at[0] += 10
    assert circuit.record_failure(ResourceExhausted())
    assert circuit.retry_after() == 110
    with pytest.raises(QuotaUnavailable):
        circuit.require_available()
    at[0] += 110
    circuit.require_available()
    for expected in (240, 480, 600, 600):
        circuit.record_failure(ResourceExhausted())
        assert circuit.retry_after() == expected
        at[0] += expected
    assert circuit.metrics()["quota_blocked"] == 1
    assert circuit.metrics()["quota_trips"] == 5
    at[0] += 1800
    circuit.record_failure(ResourceExhausted())
    assert circuit.retry_after() == 120


def test_wrapped_quota_only_not_arbitrary_errors():
    try:
        try:
            raise ResourceExhausted("sensitive")
        except ResourceExhausted as exc:
            raise RuntimeError("wrapper") from exc
    except RuntimeError as error:
        assert is_quota_error(error)
    assert not is_quota_error(RuntimeError("Quota exceeded"))
    assert not is_quota_error(PermissionError())
