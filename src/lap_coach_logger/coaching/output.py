"""Coaching output contract.

Every coaching output includes value, confidence, and reason.
No silent outputs -- everything is explainable.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class CoachingOutput:
    value: Any
    confidence: Confidence
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value if not isinstance(self.value, dict) else self.value,
            "confidence": self.confidence.value,
            "reason": self.reason,
        }
