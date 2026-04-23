"""Sync endpoint routing.

Maps envelope payload_type to the target HTTP endpoint, request shape,
and idempotency strategy. One source of truth so client.py has zero
endpoint logic baked in.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointSpec:
    path: str               # URL path, e.g. "/sessions/start"
    batch_key: str | None   # JSON body wrapper key for array payload, e.g. "laps"; None = single
    max_batch_size: int     # 1 for singletons, 50 for batched types
    idempotency_header: str # header name for idempotency key (envelope_id goes here)


_SPECS: dict[str, EndpointSpec] = {
    # All backend routes live under /v1. base_url in config should be the
    # root domain (e.g. https://api.example.com), not include /v1.
    "session": EndpointSpec(
        path="/v1/sessions-start",
        batch_key=None,
        max_batch_size=1,
        idempotency_header="Idempotency-Key",
    ),
    "session_end": EndpointSpec(
        path="/v1/sessions-end",
        batch_key=None,
        max_batch_size=1,
        idempotency_header="Idempotency-Key",
    ),
    "lap": EndpointSpec(
        path="/v1/laps-batch",
        batch_key="laps",
        max_batch_size=50,
        idempotency_header="Idempotency-Key",
    ),
    "coaching": EndpointSpec(
        path="/v1/coaching-batch",
        batch_key="coaching",
        max_batch_size=50,
        idempotency_header="Idempotency-Key",
    ),
    "event": EndpointSpec(
        path="/v1/events-batch",
        batch_key="events",
        max_batch_size=50,
        idempotency_header="Idempotency-Key",
    ),
}


def get_endpoint(payload_type: str) -> EndpointSpec | None:
    """Return the endpoint spec for a payload type, or None if unknown."""
    return _SPECS.get(payload_type)


def build_request_body(payload_type: str, envelopes: list[dict]) -> dict:
    """Assemble the HTTP request body for a batch of envelopes.

    For singleton types: returns the payload dict directly.
    For batched types: wraps under the batch_key as an array of payloads.
    """
    spec = get_endpoint(payload_type)
    if spec is None:
        raise ValueError(f"Unknown payload_type: {payload_type}")
    payloads = [e.get("payload", {}) for e in envelopes]
    if spec.batch_key is None:
        if len(payloads) != 1:
            raise ValueError(
                f"{payload_type} requires exactly 1 payload, got {len(payloads)}"
            )
        return payloads[0]
    return {spec.batch_key: payloads}


def supported_payload_types() -> list[str]:
    """Return the list of payload types that have a configured endpoint."""
    return sorted(_SPECS.keys())
