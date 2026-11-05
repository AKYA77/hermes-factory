from decimal import Decimal as D
from factory.diagnostics import diagnose_trade


def trade(side="BUY", prices=("1.1000", "1.1005", "1.0980"), flags=()):
    return {
        "side": side,
        "exit_reason": "STOP_LOSS",
        "entry_fill": {"ts": 1, "price": "1.1000"},
        "exit_fill": {"ts": 4, "price": prices[-1]},
        "stop": "1.0990" if side == "BUY" else "1.1010",
        "path": [
            {"ts": i + 1, "bid": p, "ask": str(D(p) + D(".0001"))} for i, p in enumerate(prices)
        ],
        "flags": list(flags),
    }


def test_fast_stop():
    d = diagnose_trade(trade(prices=("1.1000", "1.0990")), D(".00001"))
    assert "FAST_STOP" in d["tags"] and d["mfe"] == "0"


def test_short_liquidation_side():
    d = diagnose_trade(trade(side="SELL", prices=("1.1000", "1.0990", "1.1010")), D(".00001"))
    assert D(d["mfe"]) == D(".0009")
    assert D(d["mae"]) == D("-.0011")


def test_near_target():
    d = diagnose_trade(trade(prices=("1.1000", "1.1028", "1.0990")), D(".00001"))
    assert "TARGET_NEAR_MISS" in d["tags"]


def test_missing_path_is_not_measured():
    t = trade()
    t["path"] = []
    assert diagnose_trade(t, D(".00001"))["status"] == "INCONCLUSIVE"
    assert (
        diagnose_trade(trade(flags=("UNRESOLVED_PATH",)), D(".00001"))["status"] == "INCONCLUSIVE"
    )


def test_losing_timeout_is_not_stop_loss():
    t = trade(prices=("1.1000", "1.1005", "1.0990"))
    t["exit_reason"] = "TIMEOUT"
    t["flags"] = ["TIMEOUT"]
    d = diagnose_trade(t, D(".00001"))
    assert "FAVORABLE_THEN_STOP" not in d["tags"] and "FAST_STOP" not in d["tags"]


def test_unknown_exit_cause_is_not_inferred_from_price():
    t = trade(prices=("1.1000", "1.0990"))
    t.pop("exit_reason")
    d = diagnose_trade(t, D(".00001"))
    assert "FAST_STOP" not in d["tags"] and "EXIT_CAUSE_UNKNOWN" in d["tags"]


def test_executed_target_is_not_near_miss():
    t = trade(prices=("1.1000", "1.1028", "1.1029"))
    t["exit_reason"] = "TAKE_PROFIT"
    assert "TARGET_NEAR_MISS" not in diagnose_trade(t, D(".00001"))["tags"]


def test_mixed_partial_stop_uses_actual_fill_role_and_stop_time():
    t = trade(prices=("1.1000", "1.0990"))
    t["exit_reason"] = "MIXED"
    t["exit_fill"]["ts"] = 400 * 10**9
    t["exit_fills"] = [
        {"role": "STOP_LOSS", "ts": 10**9, "size": "2"},
        {"role": "TIMEOUT", "ts": 400 * 10**9, "size": "3"},
    ]
    value = diagnose_trade(t, D(".00001"))
    assert "FAST_STOP" in value["tags"] and "PARTIAL_STOP_LOSS_EXIT" in value["tags"]
    assert value["stop_fill_count"] == 1 and D(value["stop_filled_quantity"]) == 2


def test_exit_role_overrules_contradictory_stop_label():
    t = trade(prices=("1.1000", "1.0990"))
    t["exit_fills"] = [{"role": "TIMEOUT", "ts": 4, "size": "2"}]
    value = diagnose_trade(t, D(".00001"))
    assert "FAST_STOP" not in value["tags"]
    assert "EXIT_REASON_ROLE_MISMATCH" in value["tags"] and value["status"] == "INCONCLUSIVE"
