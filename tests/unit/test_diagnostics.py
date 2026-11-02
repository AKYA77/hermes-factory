from decimal import Decimal as D
from factory.diagnostics import diagnose_trade


def trade(side="BUY", prices=("1.1000", "1.1005", "1.0980"), flags=()):
    return {
        "side": side,
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
