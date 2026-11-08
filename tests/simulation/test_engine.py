from decimal import Decimal as D
from factory.simulation.runner import replay
from conftest import quotes


def test_engine_market_and_limit(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110350, 110360), (110400, 110410)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert not r["rejections"], r
    assert len(r["trades"]) == 1, r
    assert D(r["fills"][0]["price"]) == D("1.10035"), r
    assert D(r["fills"][1]["price"]) >= D("1.10335"), r
    assert D(r["fill_trace"][0]["slippage"]) == D(".0002")
    assert D(r["fill_trace"][1]["slippage"]) == 0


def test_short_stop_gap(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110300, 110310), (110300, 110310)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "SELL"}], True)
    assert not r["rejections"], r
    assert len(r["trades"]) == 1, r
    assert D(r["fills"][0]["price"]) == D("1.09975"), r
    assert D(r["fills"][1]["price"]) >= D("1.10335"), r
    assert D(r["trades"][0]["pnl"]) < 0


def test_T11_deadline_quote(profile, spec):
    q = quotes([(110000, 110010)] * 3, step=86400 * 10**9)
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert len(r["trades"]) == 1, r
    t = r["trades"][0]
    assert t["exit_fill"]["ts"] - t["entry_fill"]["ts"] == 86400 * 10**9
    assert "TIMEOUT" in t["flags"]


def test_missing_exit(profile, spec):
    q = quotes([(110000, 110010)] * 2)
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert not r["trades"]
    assert "NO_EXECUTABLE_EXIT_QUOTE" in r["open_trade"]["flags"]


def test_T12_measured_path(profile, spec):
    from factory.diagnostics import diagnose_trade

    q = quotes([(110000, 110010), (110000, 110010), (110100, 110110), (109800, 109810)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert len(r["trades"]) == 1, r
    d = diagnose_trade(r["trades"][0], profile.tick_size)
    assert D(d["mfe"]) == D(".00060")
    assert "FAVORABLE_THEN_STOP" in d["tags"]
    assert D(d["mae"]) < 0


def test_stop_inside_effective_spread_is_skipped(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110350, 110360)])
    small = spec.model_copy(update={"stop_ticks": 20})
    for side in ("BUY", "SELL"):
        result = replay(
            q, profile, small, [{"available_at": q[0].event_ts_utc_ns, "side": side}], True
        )
        assert not result["trades"] and not result["fills"] and not result["rejections"]
        assert result["skips"][0]["status"] == "SKIPPED_STOP_LEVEL"


def test_deadline_gap_cancels_targets_before_late_quote(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110500, 110510)], step=90000 * 10**9)
    result = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert len(result["trades"]) == 1, result
    t = result["trades"][0]
    assert t["exit_reason"] == "TIMEOUT"
    assert "DELAYED_TIMEOUT_QUOTE" in t["flags"]
    assert t["exit_fill"]["ts"] == q[-1].event_ts_utc_ns
    assert not result["integrity_errors"]


def test_equal_timestamp_quote_order_does_not_add_future_path(profile, spec):
    from dataclasses import replace

    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410), (112000, 112010)])
    q[-1] = replace(q[-1], event_ts_utc_ns=q[-2].event_ts_utc_ns)
    result = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    t = result["trades"][0]
    assert t["path"][-1]["quote_index"] == 2
    assert len(t["path"]) == 2
    assert not result["integrity_errors"]


def test_native_margin_formula_matches_profile(profile):
    from factory.simulation.runner import make_instrument
    from nautilus_trader.accounting.margin_models import StandardMarginModel

    instrument = make_instrument(profile)
    native = StandardMarginModel().calculate_margin_init(
        instrument, instrument.make_qty(1000), instrument.make_price("1.1"), D(1000)
    )
    assert native.as_decimal() == D("1.10")


def test_min_stop_distance_is_checked_against_executable_side(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110350, 110360)])
    constrained = profile.model_copy(update={"min_stop_ticks": 80})
    result = replay(
        q, constrained, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True
    )
    assert not result["fills"] and not result["rejections"]
    assert result["skips"][0]["status"] == "SKIPPED_STOP_LEVEL"


def test_canonical_profile_geometry_has_identical_native_precision(profile, spec):
    from decimal import Decimal as D
    from factory.contracts import fingerprint
    from factory.simulation.runner import make_instrument, replay
    from conftest import quotes

    padded = profile.model_copy(update={"tick_size": D("0.000010"), "volume_step": D("0.0010")})
    assert fingerprint(padded) == fingerprint(profile)
    left, right = make_instrument(profile), make_instrument(padded)
    assert left.price_precision == right.price_precision
    assert left.size_precision == right.size_precision
    data = quotes([(110000, 110010), (110000, 110010), (110600, 110610)])
    signals = [{"available_at": data[0].event_ts_utc_ns, "side": "BUY"}]
    assert replay(iter(data), profile, spec, signals, True) == replay(
        iter(data), padded, spec, signals, True
    )


def test_T08_exit_adjusts_exactly_two_pips_where_eligible(profile, spec):
    # Long stop-loss exit: entry pays the ask plus two pips, exit receives the bid
    # minus two pips, and both are reported as the adverse adjustment.
    q = quotes([(110000, 110010), (110000, 110010), (109900, 109910), (109900, 109910)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert not r["rejections"] and len(r["trades"]) == 1, r
    entry, exit_ = r["fills"]
    assert entry["role"] == "ENTRY" and D(entry["price"]) == D("1.10035")
    assert D(entry["actual_adverse_adjustment"]) == D("0.0002")
    assert exit_["role"] == "STOP_LOSS" and D(exit_["price"]) == D("1.09875")
    assert D(exit_["actual_adverse_adjustment"]) == D("0.0002")
    assert not r["integrity_errors"]

    # Short stop-loss exit mirrors the sign: entry sells the bid minus two pips,
    # exit buys the ask plus two pips.
    q = quotes([(110000, 110010), (110000, 110010), (110100, 110110), (110100, 110110)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "SELL"}], True)
    assert not r["rejections"] and len(r["trades"]) == 1, r
    entry, exit_ = r["fills"]
    assert entry["role"] == "ENTRY" and D(entry["price"]) == D("1.09975")
    assert D(entry["actual_adverse_adjustment"]) == D("0.0002")
    assert exit_["role"] == "STOP_LOSS" and D(exit_["price"]) == D("1.10135")
    assert D(exit_["actual_adverse_adjustment"]) == D("0.0002")
    assert not r["integrity_errors"]


def test_T08_limit_exit_has_no_adverse_adjustment(profile, spec):
    # A take-profit limit guarantees its price, so no adverse adjustment applies.
    q = quotes([(110000, 110010), (110000, 110010), (110350, 110360), (110400, 110410)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert not r["rejections"] and len(r["trades"]) == 1, r
    entry, exit_ = r["fills"]
    assert entry["role"] == "ENTRY" and D(entry["actual_adverse_adjustment"]) == D("0.0002")
    assert exit_["role"] == "TAKE_PROFIT"
    assert "actual_adverse_adjustment" not in exit_
    assert D(r["fill_trace"][1]["slippage"]) == 0
    assert not r["integrity_errors"]


def test_T09_limit_never_exceeds_limit_price(profile, spec):
    # A SELL take-profit must fill at or above its target; the runner flags any
    # fill beyond the limit price as an integrity error.
    q = quotes([(110000, 110010), (110000, 110010), (110350, 110360), (110400, 110410)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert not r["rejections"] and len(r["trades"]) == 1, r
    exit_ = r["fills"][1]
    assert exit_["role"] == "TAKE_PROFIT"
    assert D(exit_["price"]) >= D(r["trades"][0]["target"])
    assert not r["integrity_errors"]


def test_T09_stop_gap_is_recognized(profile, spec):
    # Price gaps through the stop, so the exit fills worse than the stop level.
    q = quotes([(110000, 110010), (110000, 110010), (109000, 109010), (109000, 109010)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert not r["rejections"] and len(r["trades"]) == 1, r
    trade = r["trades"][0]
    assert D(trade["stop"]) == D("1.09935")
    assert D(r["fills"][1]["price"]) < D(trade["stop"])
    assert r["fills"][1]["role"] == "STOP_LOSS"
    assert not r["integrity_errors"]


def test_T09_timeout_quote_absence_is_flagged(profile, spec):
    q = quotes([(110000, 110010)] * 3, step=86400 * 10**9)
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    assert len(r["trades"]) == 1, r
    assert "TIMEOUT" in r["trades"][0]["flags"]
    assert not r["integrity_errors"]
