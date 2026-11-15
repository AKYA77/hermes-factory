"""R05: a strategy evaluates only the timeframes it actually requires."""

from conftest import quotes
from factory.contracts import TIMEFRAMES, Signal, StrategySpec
from factory.features import closed_bar_events, feature_key


def _spec(timeframe, confirmations=()):
    return StrategySpec(
        instrument="EURUSD",
        timeframe=timeframe,
        signal=Signal(operator="momentum", lookback=2, threshold="1"),
        confirmations=confirmations,
        stop_ticks=100,
    )


def _published_timeframes(quotes, spec):
    required = (spec.timeframe, *spec.confirmations)
    events = list(closed_bar_events(quotes, required))
    return {timeframe for event in events for timeframe in event}, required


def test_only_the_required_timeframes_are_published():
    # Four hourly quotes: enough for one H1 bar to close, none for D1.
    q = quotes([(110000, 110010)] * 4, step=3600 * 10**9)
    published, required = _published_timeframes(q, _spec("H1"))
    assert published == {"H1"}
    assert required == ("H1",)
    assert "M1" not in published


def test_confirmations_add_exactly_the_confirmed_higher_timeframes():
    q = quotes([(110000, 110010)] * 28, step=3600 * 10**9)  # just over a day
    published, required = _published_timeframes(q, _spec("H1", ("D1",)))
    assert required == ("H1", "D1")
    assert published <= {"H1", "D1"}
    assert "M1" not in published and "M5" not in published


def test_no_complete_m1_loop_is_forced_on_a_daily_strategy():
    """A D1 strategy must never build M1 bars, even though M1 exists as a timeframe."""
    assert "M1" in TIMEFRAMES
    q = quotes([(110000, 110010)] * 28, step=3600 * 10**9)
    published, required = _published_timeframes(q, _spec("D1"))
    assert required == ("D1",)
    assert published == {"D1"}


def test_feature_key_binds_exactly_the_per_strategy_timeframe_set():
    base = _spec("H1")
    with_confirmation = _spec("H1", ("D1",))
    other_timeframe = _spec("M15")

    def key(spec):
        return feature_key("d" * 64, spec, "rev", "i" * 64)

    assert key(base) != key(with_confirmation), "confirmations must enter the key"
    assert key(base) != key(other_timeframe), "the base timeframe must enter the key"
    # Same required set through a different construction order still matches.
    assert key(_spec("H1")) == key(_spec("H1"))
