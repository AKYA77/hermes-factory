from decimal import Decimal as D
import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, Window, fingerprint
from factory.features import feature_key, BoundedCache
from factory.improvement import children
from factory.experiments import Store
from factory.validation import evidence_status, quarter_folds, purge, wilson
from factory.simulation.pricing import effective_quotes, eligible_price, size_position
from datetime import datetime, timezone


def contract(spec, profile):
    return ExperimentContract(
        strategy_hash=spec.strategy_hash,
        dataset_hash="a" * 64,
        instrument_hash=fingerprint(profile),
        engine_version="1.231.0",
        code_revision="fixture",
        fill_version="adverse-fill/v1",
        evaluation_policy="test/v1",
        scenario="historical-pessimistic/v1",
        windows=(Window(start_ns=1, end_ns=10, role="train_only"),),
        seed=42,
    )


def test_T01_normalization(spec):
    a = spec.model_dump()
    a["signal"]["threshold"] = D("1.000")
    assert StrategySpec.model_validate(a).strategy_hash == spec.strategy_hash
    for k, v in [("timeframe", "M5"), ("stop_ticks", 101)]:
        a = spec.model_dump()
        a[k] = v
        assert StrategySpec.model_validate(a).strategy_hash != spec.strategy_hash
    with pytest.raises(ValidationError):
        StrategySpec.model_validate({**spec.model_dump(), "executable": "rm -rf"})


def test_T02_fingerprint(spec, profile):
    c = contract(spec, profile)
    for field, value in [
        ("dataset_hash", "b" * 64),
        ("fill_version", "v2"),
        ("code_revision", "new"),
        ("engine_version", "new"),
    ]:
        assert c.model_copy(update={field: value}).experiment_hash != c.experiment_hash
    assert feature_key("a", spec, "v1", "p") != feature_key("b", spec, "v1", "p")


@given(st.integers(1, 100))
def test_T07_spread(width):
    from factory.instruments import synthetic_profile

    profile = synthetic_profile("EURUSD")
    bid = D("1.10000")
    ask = bid + width * profile.tick_size
    b, a = effective_quotes(bid, ask, profile, True)
    assert a - b >= max(ask - bid, 2 * profile.pip_size)
    if width >= 20:
        assert (b, a) == (bid, ask)


@pytest.mark.parametrize("side,expected", [("BUY", "1.1002"), ("SELL", "1.0998")])
def test_T08_arithmetic(profile, side, expected):
    assert eligible_price(D("1.1"), side, "MARKET", profile, True) == D(expected)
    assert eligible_price(D("1.1"), side, "STOP_MARKET", profile, True) == D(expected)
    assert eligible_price(D("1.1"), side, "LIMIT", profile, True, limit=D("1.1")) == D("1.1")


def test_T10_risk(profile):
    result = size_position(D(20), D("1.1"), D("1.099"), profile, D(1))
    assert result["risk"] <= 2
    p = profile.model_copy(update={"min_volume": D(10000)})
    assert size_position(D(20), D("1.1"), D("1.099"), p, D(1))["status"] == "SKIPPED_MIN_VOLUME"


def test_T13_lineage(tmp_path, spec):
    store = Store(tmp_path / "db")
    parent = store.register_strategy(spec)
    for child, reason in children(spec):
        store.register_strategy(child, parent, reason)
        row = store.rows(
            "SELECT * FROM strategy_specs WHERE strategy_id=?", (child.strategy_hash,)
        )[0]
        assert row["parent_id"] == parent
        assert row["changed_fields"] != "[]"
        assert child.target_rr == "3"
    assert store.rows("SELECT * FROM strategy_specs WHERE strategy_id=?", (parent,))


def test_T14_negative_evidence():
    assert evidence_status(100, 100, False, True, False) == "OOS_FAILED"
    assert evidence_status(100, 100, True, True, True) == "INSUFFICIENT_EVIDENCE"
    assert evidence_status(100, 100, True, False, False) == "FAILED_CHECKS"


def test_T15_quarters():
    def ns(s):
        return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1e9)

    f = list(quarter_folds(ns("2025-01-01"), ns("2025-11-02")))
    assert f[0]["train_end"] == ns("2025-04-01")
    assert f[0]["oos_end"] == ns("2025-07-01")
    assert f[-1]["partial"]
    assert purge([{"entry_fill": {"ts": 1}, "exit_fill": {"ts": 12}}], 0, 10) == []
    assert wilson(0, 0) is None


def test_T26_unknown_units(profile):
    p = profile.model_dump()
    p["pip_size"] = D(".000015")
    with pytest.raises(ValidationError):
        InstrumentSpec.model_validate(p)


def test_bounded_cache():
    import numpy as np

    cache = BoundedCache(16)
    cache.put("a", np.array([1, 2], dtype="int64"))
    assert not cache.get("a").flags.writeable
    cache.put("b", np.array([3, 4], dtype="int64"))
    assert cache.get("a") is None
    assert cache.evictions == 1


def test_currency_identity_cannot_disguise_jpy_as_usd(profile):
    raw = profile.model_dump()
    raw["instrument"] = "USDJPY"
    with pytest.raises(ValidationError, match="currency identity"):
        InstrumentSpec.model_validate(raw)


def test_max_volume_cap_is_rounded_down_to_step(profile):
    p = profile.model_copy(
        update={"max_volume": D("1.005"), "volume_step": D(".01"), "min_volume": D(".01")}
    )
    result = size_position(D(20), D("1.1"), D("1.099"), p, D(1))
    assert result["status"] == "ELIGIBLE"
    assert result["size"] == D("1.00") and result["size"] % p.volume_step == 0
    assert result["risk"] <= 2


def test_quarter_boundary_never_rounds_a_nanosecond_into_future():
    cut = int(datetime(2025, 4, 1, tzinfo=timezone.utc).timestamp()) * 10**9
    end = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp()) * 10**9
    first = next(quarter_folds(cut - 1, end))
    assert first["train_end"] == cut


def test_decimal_identity_preserves_all_digits_independently_of_arithmetic_context():
    from decimal import Decimal, localcontext
    from factory.contracts import canonical, fingerprint

    left = Decimal("1.0000000000000000000000000001")
    right = Decimal("1.0000000000000000000000000002")
    assert fingerprint({"v": left}) != fingerprint({"v": right})
    for precision in (2, 6, 28, 60):
        with localcontext() as context:
            context.prec = precision
            assert canonical(left) == "1.0000000000000000000000000001"
            assert canonical(Decimal("1.23456789")) == "1.23456789"
            assert (
                fingerprint({"value": Decimal("1.23456789")})
                == "8f85642ee24c1d6cc777b89e4c1a4278fbafbbe7faa479a537bed3e8ee8fe227"
            )
            assert canonical(Decimal("1000.000")) == "1000"
            assert canonical(Decimal("0.0000100")) == "0.00001"
            assert canonical(Decimal("-0.000")) == "-0"
            assert fingerprint({"v": Decimal("1.2300")}) == fingerprint({"v": Decimal("1.23")})


def test_exact_decimal_encoding_matches_legacy_for_representable_values():
    from decimal import Decimal, localcontext
    from factory.contracts import canonical

    for raw in (
        "1",
        "20.00",
        "0.1",
        "1000000",
        "1e-12",
        "-125.000",
        "-0.00",
        "1234567890123456789012345678",
        "100000000000000000000000000000000000",
    ):
        value = Decimal(raw)
        with localcontext() as context:
            context.prec = 28
            legacy = format(value.normalize(), "f")
        assert canonical(value) == legacy


def test_canonical_decimal_expansion_is_bounded_before_formatting():
    from decimal import Decimal
    import pytest
    from factory.contracts import fingerprint

    for value in (Decimal("1e1000000000"), Decimal("1e-1000000000")):
        with pytest.raises(ValueError, match="CANONICAL_DECIMAL_RESOURCE_LIMIT"):
            fingerprint({"v": value})


def test_windows_reject_ambiguous_floating_and_boolean_nanoseconds():
    from factory.contracts import Window
    import pytest

    for bad in (True, 1.0, 1735689600000000000.0, "1e18"):
        with pytest.raises(ValueError, match="exact integer nanoseconds"):
            Window(start_ns=bad, end_ns=1735689600000000001, role="train_only")
    precise = Window(
        start_ns="1735689600000000001", end_ns="1735689600000000002", role="train_only"
    )
    assert precise.end_ns - precise.start_ns == 1
