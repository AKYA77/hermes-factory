"""Independent index-based label reference, not a second matching engine."""

from decimal import Decimal as D
from fractions import Fraction

import pytest

from factory.contracts import ExperimentContract, Signal, StrategySpec, Window, fingerprint
from factory.features import Bar
from factory.instruments import synthetic_profile
from factory.screening.labels import CostHorizonPolicy, estimate_labels
from factory.strategies import iter_bar_signals


def inputs(operator="momentum", symbol="EURUSD", prices=None, times=None):
    profile = synthetic_profile(symbol)
    start = 1735689600 * 10**9
    prices = prices if prices is not None else [D(100) + D(n % 9) / 100 for n in range(100)]
    times = (
        times if times is not None else [start + (n + 1) * 60 * 10**9 for n in range(len(prices))]
    )
    bars = [Bar(end, end + 1, D(price), D(price), D(price)) for end, price in zip(times, prices)]
    spec = StrategySpec(
        instrument=symbol,
        timeframe="M1",
        signal=Signal(operator=operator, lookback=2, threshold=".5"),
        stop_ticks=100,
    )
    contract = ExperimentContract(
        strategy_hash=spec.strategy_hash,
        dataset_hash="a" * 64,
        instrument_hash=fingerprint(profile),
        engine_version="test",
        code_revision="test-only-source",
        fill_version="test-only-no-native-matching",
        evaluation_policy="test-only-training",
        scenario="historical-pessimistic/v1",
        windows=(Window(start_ns=start, end_ns=times[-1] + 2, role="train_only"),),
        seed=1,
    )
    return profile, spec, contract, bars


@pytest.mark.parametrize("operator", ["momentum", "mean_reversion", "breakout"])
def test_streaming_estimator_matches_independent_fixed_index_reference(operator):
    profile, spec, contract, bars = inputs(operator)
    policy = CostHorizonPolicy(horizon_bars=3, min_labels=2, max_censored_fraction="1")
    events = [{"M1": bar} for bar in bars]
    signals = list(iter_bar_signals(events, spec))
    by_available = {bar.available_at: n for n, bar in enumerate(bars)}
    reference = []
    for signal in signals:
        origin = by_available[signal["available_at"]]
        if origin + 3 < len(bars):
            sign = 1 if signal["side"] == "BUY" else -1
            reference.append(
                (Fraction(bars[origin + 3].close) - Fraction(bars[origin].close))
                * sign
                / Fraction(profile.pip_size)
                - 6
            )
    result = estimate_labels(iter(events), spec, profile, contract, policy)
    assert result["signal_count"] == len(signals)
    assert result["label_count"] == len(reference) > 2
    assert result["end_censored_labels"] == len(signals) - len(reference)
    mean = sum(reference) / len(reference)
    expected = D(mean.numerator) / D(mean.denominator)
    assert D(result["mean_net_label_pips"]) == expected
    assert result["max_pending_labels"] <= 3
    assert result["pruning_authorized"] is False
    assert not {"trades", "fills", "equity", "validated"} & result.keys()


def test_cost_proxy_can_suggest_rejection_but_never_authorizes_pruning():
    prices = [D("1.1") + D(n) * D(".00001") for n in range(100)]
    profile, spec, contract, bars = inputs(prices=prices)
    policy = CostHorizonPolicy(horizon_bars=1, min_labels=50)
    result = estimate_labels(({"M1": bar} for bar in bars), spec, profile, contract, policy)
    assert result["rejection_suggested"] and result["pruning_authorized"] is False
    assert D(result["mean_net_label_pips"]) == D("-5.9")
    assert result["population_label_variance_pips"] == "0"
    reference = contract.model_copy(update={"scenario": "historical-reference/v1"})
    free = estimate_labels(({"M1": bar} for bar in bars), spec, profile, reference, policy)
    assert D(free["mean_net_label_pips"]) == D(".1") and not free["rejection_suggested"]


@pytest.mark.parametrize("symbol", ["EURUSD", "USDJPY", "XAUUSD"])
def test_declared_unit_scaling_and_no_end_of_sample_outcome_fabrication(symbol):
    profile = synthetic_profile(symbol)
    prices = [D(100) + n * profile.pip_size for n in range(20)]
    profile, spec, contract, bars = inputs(symbol=symbol, prices=prices)
    result = estimate_labels(
        ({"M1": bar} for bar in bars),
        spec,
        profile,
        contract,
        CostHorizonPolicy(horizon_bars=100, min_labels=2),
    )
    assert result["signal_count"] and result["label_count"] == 0
    assert result["signal_count"] == result["end_censored_labels"]
    assert result["mean_net_label_pips"] is None and not result["rejection_suggested"]


def test_sparse_over_24h_features_censor_labels_and_never_create_exits():
    start = 1735689600 * 10**9
    prices = [D("1.1") + D(n) / 10000 for n in range(20)]
    times = [start + n * 2 * 86400 * 10**9 for n in range(1, 21)]
    profile, spec, contract, bars = inputs(prices=prices, times=times)
    result = estimate_labels(
        ({"M1": bar} for bar in bars),
        spec,
        profile,
        contract,
        CostHorizonPolicy(horizon_bars=1, min_labels=2),
    )
    assert result["time_censored_labels"] > 0 and result["label_count"] == 0
    assert not result["rejection_suggested"]


def test_unavailable_outside_training_and_evaluation_inputs_reject():
    profile, spec, contract, bars = inputs()
    policy = CostHorizonPolicy()
    outside = contract.model_copy(
        update={
            "windows": (contract.windows[0].model_copy(update={"role": "final_holdout_unseen"}),)
        }
    )
    with pytest.raises(ValueError, match="authorized training"):
        estimate_labels(({"M1": bar} for bar in bars), spec, profile, outside, policy)
    with pytest.raises(ValueError, match="outside authorized training"):
        estimate_labels(
            ({"M1": bar} for bar in bars),
            spec,
            profile,
            contract.model_copy(
                update={
                    "windows": (
                        contract.windows[0].model_copy(update={"end_ns": bars[-1].available_at}),
                    )
                }
            ),
            policy,
        )
    invalid = Bar(bars[0].end_ns, bars[0].end_ns - 1, D(1), D(1), D(1))
    with pytest.raises(ValueError, match="unavailable closed"):
        estimate_labels(iter([{"M1": invalid}]), spec, profile, contract, policy)
