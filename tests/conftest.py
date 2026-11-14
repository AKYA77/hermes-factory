import pytest
from factory.contracts import Signal, StrategySpec
from factory.data import Quote
from factory.instruments import synthetic_profile


@pytest.fixture
def profile():
    return synthetic_profile("EURUSD")


@pytest.fixture
def spec():
    return StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=2, threshold="1"),
        stop_ticks=100,
    )


def quotes(values, step=10**9, start=1735689600 * 10**9):
    return [
        Quote("EURUSD", start + i * step, b, a, 100000, "synthetic", "fixture", i)
        for i, (b, a) in enumerate(values)
    ]
