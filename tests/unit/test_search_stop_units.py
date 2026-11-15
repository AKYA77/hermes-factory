"""Sampling units are declared profile facts, never inferred from quote digits."""

from decimal import Decimal as D

import pytest

from factory.contracts import SYMBOLS, Window
from factory.exploration.persistent import SearchProtocol
from factory.instruments import synthetic_profile


def protocol(profile, **changes):
    return SearchProtocol(
        dataset_hash="a" * 64,
        profile=profile,
        window=Window(start_ns=1, end_ns=2, role="train_only"),
        family="momentum",
        timeframe="M1",
        code_revision="explicit synthetic sampling test",
        seed=42,
        **changes,
    )


@pytest.mark.parametrize("symbol", sorted(SYMBOLS))
def test_v3_sample_range_uses_declared_pips_and_broker_stop_level(symbol):
    p = protocol(synthetic_profile(symbol))
    stop = p.stop_distribution()
    assert p.schema_version == "search/v3"
    assert stop.step * p.profile.tick_size == p.profile.pip_size
    assert stop.low * p.profile.tick_size >= (
        4 * p.profile.pip_size + (1 + p.profile.min_stop_ticks) * p.profile.tick_size
    )
    assert (stop.high - stop.low) // stop.step == 18


def test_gold_precision_does_not_change_pip_and_legacy_ranges_stay_exact():
    gold = synthetic_profile("XAUUSD").model_copy(
        update={
            "tick_size": D(".001"),
            "pip_size": D(".1"),
            "price_scale": 1000,
            "source": "synthetic declared pip distinct from empirical grid; not broker facts",
        }
    )
    modern = protocol(gold)
    dist = modern.stop_distribution()
    assert (dist.low, dist.high, dist.step) == (500, 2300, 100)
    assert modern.profile.pip_size == D(".1")
    for version in ("search/v1", "search/v2"):
        legacy = protocol(gold, schema_version=version)
        original = legacy.stop_distribution()
        assert (original.low, original.high, original.step) == (20, 200, 10)
        assert legacy.protocol_hash != modern.protocol_hash


def test_v3_reference_costs_and_large_stop_level_are_explicit():
    profile = synthetic_profile("EURUSD").model_copy(update={"min_stop_ticks": 100})
    conservative = protocol(profile).stop_distribution()
    reference = protocol(profile, scenario="historical-reference/v1").stop_distribution()
    assert conservative.low == 150 and reference.low == 100
    impossible = profile.model_copy(update={"min_stop_ticks": 1_000_001})
    with pytest.raises(ValueError, match="no representable stop"):
        protocol(impossible)
