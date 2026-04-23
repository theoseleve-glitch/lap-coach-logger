"""Tests for sync endpoint router."""
from __future__ import annotations

import pytest

from lap_coach_logger.sync.endpoints import (
    EndpointSpec,
    build_request_body,
    get_endpoint,
    supported_payload_types,
)


def test_session_is_singleton():
    spec = get_endpoint("session")
    assert spec is not None
    assert spec.batch_key is None
    assert spec.max_batch_size == 1
    assert spec.path == "/v1/sessions-start"


def test_session_end_is_singleton():
    spec = get_endpoint("session_end")
    assert spec.path == "/v1/sessions-end"
    assert spec.batch_key is None


def test_lap_is_batched():
    spec = get_endpoint("lap")
    assert spec.batch_key == "laps"
    assert spec.max_batch_size == 50


def test_coaching_is_batched():
    spec = get_endpoint("coaching")
    assert spec.path == "/v1/coaching-batch"
    assert spec.batch_key == "coaching"


def test_event_is_batched():
    spec = get_endpoint("event")
    assert spec.path == "/v1/events-batch"
    assert spec.batch_key == "events"


def test_unknown_payload_type_returns_none():
    assert get_endpoint("unknown_type") is None


def test_build_singleton_body_returns_payload_directly():
    envelope = {"envelope_id": "e1", "payload_type": "session", "payload": {"session_id": "s1"}}
    body = build_request_body("session", [envelope])
    assert body == {"session_id": "s1"}


def test_build_singleton_rejects_multiple():
    envelopes = [
        {"envelope_id": "e1", "payload_type": "session", "payload": {"session_id": "s1"}},
        {"envelope_id": "e2", "payload_type": "session", "payload": {"session_id": "s2"}},
    ]
    with pytest.raises(ValueError, match="exactly 1"):
        build_request_body("session", envelopes)


def test_build_batch_body_wraps_in_array():
    envelopes = [
        {"envelope_id": "e1", "payload_type": "lap", "payload": {"lap_number": 1}},
        {"envelope_id": "e2", "payload_type": "lap", "payload": {"lap_number": 2}},
    ]
    body = build_request_body("lap", envelopes)
    assert body == {"laps": [{"lap_number": 1}, {"lap_number": 2}]}


def test_build_batch_with_empty_list_returns_empty_array():
    body = build_request_body("lap", [])
    assert body == {"laps": []}


def test_build_body_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown payload_type"):
        build_request_body("xxx", [])


def test_supported_types_lists_all_five():
    types = supported_payload_types()
    assert set(types) == {"session", "session_end", "lap", "coaching", "event"}


def test_idempotency_header_is_consistent():
    for t in supported_payload_types():
        spec = get_endpoint(t)
        assert spec.idempotency_header == "Idempotency-Key"
