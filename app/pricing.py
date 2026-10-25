"""Token usage accounting and USD cost (Lecture 11 prices for gpt-6-luna)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.config import MODEL

# USD per 1M tokens.
PRICES_PER_M: dict[str, dict[str, float]] = {
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50},
}


def _get(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


@dataclass
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # already included in output_tokens
    # Fields the API response did NOT report. Their int value above is 0 only so totals can be
    # added up; ledgers write them as null, so a missing value is never presented as a measured 0.
    missing: tuple[str, ...] = field(default=(), compare=False)

    @property
    def uncached_input_tokens(self) -> int:
        return max(0, self.input_tokens - self.cached_tokens - self.cache_write_tokens)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        if not isinstance(other, Usage):
            return NotImplemented
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            missing=tuple(sorted(set(self.missing) | set(other.missing))),
        )

    def __radd__(self, other: Any) -> Usage:
        # Lets sum(usages) work with its default start value of 0.
        if other == 0:
            return self + Usage()
        return NotImplemented

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_tokens": self.cached_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "uncached_input_tokens": self.uncached_input_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_api(cls, usage: Any) -> Usage:
        """Map a Responses API usage object (SDK model or dict) to Usage.

        A field the response does not report is listed in ``missing`` (its int is 0 only for
        arithmetic). Flat dicts such as ledger records (``cached_tokens`` at the top level) work too.
        """
        if usage is None:
            return cls(missing=USAGE_FIELDS)
        input_details = _get(usage, "input_tokens_details")
        output_details = _get(usage, "output_tokens_details")
        missing: list[str] = []

        def top(name: str) -> int:
            value = _get(usage, name)
            if value is None:
                missing.append(name)
            return _count(value)

        def detail(details: Any, name: str) -> int:
            value = _get(details, name)
            if value is None:
                value = _get(usage, name)
            if value is None:
                missing.append(name)
            return _count(value)

        return cls(
            input_tokens=top("input_tokens"),
            cached_tokens=detail(input_details, "cached_tokens"),
            cache_write_tokens=detail(input_details, "cache_write_tokens"),
            output_tokens=top("output_tokens"),
            reasoning_tokens=detail(output_details, "reasoning_tokens"),
            missing=tuple(missing),
        )


USAGE_FIELDS = ("input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens")
# Without these two the cost of a call cannot be computed at all.
COST_CRITICAL_FIELDS = ("input_tokens", "output_tokens")


def cost_usd(usage: Usage, model: str = MODEL) -> float:
    """Unrounded USD cost. Uncached input = input - cached - cache_write, billed at the input rate."""
    try:
        prices = PRICES_PER_M[model]
    except KeyError:
        raise ValueError(f"no prices configured for model {model!r}") from None
    return (
        usage.uncached_input_tokens * prices["input"]
        + usage.cached_tokens * prices["cached_input"]
        + usage.cache_write_tokens * prices["cache_write"]
        + usage.output_tokens * prices["output"]
    ) / 1_000_000
