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
