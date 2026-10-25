from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import MODEL
from app.pricing import PRICES_PER_M, Usage, cost_usd

# Usage exactly as returned by Portkey -> gpt-6-luna in the 2026-10-25 probe (DESIGN.md §2).
SDK_USAGE = {
    "input_tokens": 4036,
    "input_tokens_details": {"cached_tokens": 4014, "cache_write_tokens": 19},
    "output_tokens": 22,
    "output_tokens_details": {"reasoning_tokens": 0},
    "total_tokens": 4058,
}

USAGE_KEYS = {
    "input_tokens",
    "cached_tokens",
    "cache_write_tokens",
    "output_tokens",
    "reasoning_tokens",
    "uncached_input_tokens",
    "total_tokens",
}


def test_prices_match_lecture_11():
    assert PRICES_PER_M[MODEL] == {"input": 0.10, "cached_input": 0.01, "cache_write": 0.125, "output": 0.50}


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        (Usage(input_tokens=1_000_000), 0.10),
        (Usage(input_tokens=1_000_000, cached_tokens=1_000_000), 0.01),
        (Usage(input_tokens=1_000_000, cache_write_tokens=1_000_000), 0.125),
        (Usage(output_tokens=1_000_000), 0.50),
        (Usage(), 0.0),
    ],
)
def test_cost_per_token_class(usage: Usage, expected: float):
    assert cost_usd(usage) == pytest.approx(expected)


def test_cost_formula_with_cache_read_and_write():
    usage = Usage(input_tokens=4036, cached_tokens=4014, cache_write_tokens=19, output_tokens=22)
    # uncached input = 4036 - 4014 - 19 = 3, billed at the input rate
    expected = (3 * 0.10 + 4014 * 0.01 + 19 * 0.125 + 22 * 0.50) / 1_000_000
    assert usage.uncached_input_tokens == 3
    assert cost_usd(usage) == pytest.approx(expected, rel=1e-12)
    assert cost_usd(usage, MODEL) == pytest.approx(expected, rel=1e-12)


def test_reasoning_tokens_are_not_billed_twice():
    with_reasoning = Usage(input_tokens=100, output_tokens=500, reasoning_tokens=400)
    without = Usage(input_tokens=100, output_tokens=500)
    assert cost_usd(with_reasoning) == pytest.approx(cost_usd(without))


def test_uncached_input_never_negative():
    assert Usage(input_tokens=10, cached_tokens=8, cache_write_tokens=5).uncached_input_tokens == 0


def test_total_tokens_is_input_plus_output():
    assert Usage(input_tokens=1200, output_tokens=300, reasoning_tokens=100).total_tokens == 1500


def test_usage_addition_sums_every_field():
    a = Usage(input_tokens=1, cached_tokens=2, cache_write_tokens=3, output_tokens=4, reasoning_tokens=5)
    b = Usage(input_tokens=10, cached_tokens=20, cache_write_tokens=30, output_tokens=40, reasoning_tokens=50)
    total = a + b
    assert total == Usage(input_tokens=11, cached_tokens=22, cache_write_tokens=33, output_tokens=44, reasoning_tokens=55)
    assert a == Usage(input_tokens=1, cached_tokens=2, cache_write_tokens=3, output_tokens=4, reasoning_tokens=5)


def test_to_dict_has_all_fields_and_derived_values():
    d = Usage(input_tokens=4036, cached_tokens=4014, cache_write_tokens=19, output_tokens=22).to_dict()
    assert set(d) == USAGE_KEYS
    assert d["uncached_input_tokens"] == 3
    assert d["total_tokens"] == 4058


def test_from_api_on_probe_shaped_dict():
    u = Usage.from_api(SDK_USAGE)
    assert u == Usage(input_tokens=4036, cached_tokens=4014, cache_write_tokens=19, output_tokens=22, reasoning_tokens=0)
    assert u.total_tokens == SDK_USAGE["total_tokens"]


def test_from_api_on_attribute_object():
    obj = SimpleNamespace(
        input_tokens=500,
        input_tokens_details=SimpleNamespace(cached_tokens=300, cache_write_tokens=100),
        output_tokens=80,
        output_tokens_details=SimpleNamespace(reasoning_tokens=30),
        total_tokens=580,
    )
    assert Usage.from_api(obj) == Usage(500, 300, 100, 80, 30)


def test_from_api_on_real_sdk_model():
    responses_types = pytest.importorskip("openai.types.responses")
    sdk_usage = responses_types.ResponseUsage.model_validate(SDK_USAGE)
    assert Usage.from_api(sdk_usage) == Usage(4036, 4014, 19, 22, 0)


@pytest.mark.parametrize(
    "raw",
    [None, {}, {"input_tokens": 0}, {"input_tokens_details": None, "output_tokens_details": None}],
)
def test_from_api_missing_fields_are_zero(raw):
    assert Usage.from_api(raw) == Usage()


def test_from_api_partial_dict():
    u = Usage.from_api({"input_tokens": 50, "output_tokens": 7})
    assert u == Usage(input_tokens=50, output_tokens=7)
