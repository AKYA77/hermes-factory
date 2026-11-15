from decimal import Decimal as D
import pytest
from factory.simulation.ledger import Fill, TradeLedger


def ledger(side="BUY"):
    obj = TradeLedger({"side": side, "flags": []}, D(10))
    for oid, role in [("e", "ENTRY"), ("s", "STOP_LOSS"), ("t", "TAKE_PROFIT"), ("x", "TIMEOUT")]:
        obj.register(oid, role)
    return obj


def fill(oid, tid, side, qty, px, ts=1):
    return Fill(oid, tid, ts, side, D(qty), D(px))


def test_partial_entries_are_not_exits_and_weighted():
    book = ledger()
    book.apply(fill("e", "1", "BUY", "4", "1.1"))
    book.apply(fill("e", "2", "BUY", "6", "1.2", 2))
    book.terminal("e", "FILLED")
    assert book.quantity == 10 and not book.closed
    assert book.aggregate(True)["price"] == "1.16"
    book.apply(fill("t", "3", "SELL", "3", "1.4", 3))
    assert book.quantity == 7 and not book.closed
    book.apply(fill("s", "4", "SELL", "7", "1.0", 4))
    assert book.closed and book.realized == D("-.40") and book.cost == 0
    assert book.snapshot()["exit_reason"] == "MIXED"
    assert book.snapshot()["exit_fill"]["order_id"] is None


def test_partially_filled_then_canceled_entry_closes_actual_quantity():
    book = ledger()
    book.apply(fill("e", "1", "BUY", "4", "1.1"))
    book.terminal("e", "CANCELED")
    book.apply(fill("s", "2", "SELL", "4", "1", 2))
    assert book.closed and book.snapshot()["entered_quantity"] == "4"
    assert book.realized == D("-.4")


def test_duplicate_fill_idempotent_and_conflict_rejected():
    book = ledger()
    f = fill("e", "1", "BUY", "4", "1.1")
    book.apply(f)
    assert book.apply(f) == 0 and book.entered == 4
    with pytest.raises(ValueError, match="CONFLICTING_DUPLICATE"):
        book.apply(fill("e", "1", "BUY", "5", "1.1"))
    assert book.entered == 4


@pytest.mark.parametrize(
    "case,reason",
    [
        (("unknown", "a", "BUY", "1", "1.1"), "UNKNOWN_FILL_ORDER"),
        (("e", "a", "SELL", "1", "1.1"), "FILL_SIDE_MISMATCH"),
        (("e", "a", "BUY", "11", "1.1"), "ENTRY_OVERFILL"),
        (("s", "a", "SELL", "1", "1.1"), "EXIT_OVERFILL"),
    ],
)
def test_invalid_fills_do_not_mutate_ledger(case, reason):
    book = ledger()
    with pytest.raises(ValueError, match=reason):
        book.apply(fill(*case))
    assert not book.fills and book.quantity == 0 and book.realized == 0


def test_short_partial_pnl_and_fill_order():
    book = ledger("SELL")
    book.apply(fill("e", "1", "SELL", "10", "1.2", 2))
    book.terminal("e", "FILLED")
    with pytest.raises(ValueError, match="OUT_OF_ORDER"):
        book.apply(fill("t", "bad", "BUY", "2", "1", 1))
    book.apply(fill("t", "2", "BUY", "3", "1.1", 3))
    book.apply(fill("t", "3", "BUY", "7", "1.0", 4))
    assert book.closed and book.realized == D("1.7")
    assert book.snapshot()["exit_reason"] == "TAKE_PROFIT"


def test_fees_and_remainder_cash_reconcile_exactly():
    book = ledger()
    book.apply(fill("e", "1", "BUY", "3", "1.10001"))
    book.apply(fill("e", "2", "BUY", "7", "1.20002", 2))
    book.terminal("e", "FILLED")
    for i in range(10):
        book.apply(fill("x", str(i), "SELL", "1", "1.30003", 3 + i))
    assert book.closed and book.realized == D("1.30013") and book.cost == 0


def test_commission_accounting_uses_every_actual_fill():
    book = ledger()
    book.apply(Fill("e", "e1", 1, "BUY", D(10), D(1), D(".1")))
    book.terminal("e", "FILLED")
    book.apply(Fill("t", "t1", 2, "SELL", D(10), D("1.1"), D(".2")))
    assert book.closed and book.realized == D(".7") and book.fees == D(".3")


def test_interleaved_entry_exit_fill_order_and_cash_preserved():
    book = ledger()
    book.apply(fill("e", "1", "BUY", "4", "1.1"))
    book.apply(fill("t", "2", "SELL", "2", "1.2"))
    book.apply(fill("e", "3", "BUY", "6", "1.3"))
    book.terminal("e", "FILLED")
    book.apply(fill("s", "4", "SELL", "8", "1.0"))
    assert book.closed and book.realized == D("-1.8")
    assert [f["order_id"] for f in book.snapshot()["execution_fills"]] == ["e", "t", "e", "s"]
