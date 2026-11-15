"""Tests for the crossed-quote quarantine policy.

The measured defect is USDCAD July 2026: 353 crossed quotes in 1,226,412 rows
(0.029%), crossing by 1-7 pips at the provider's 1e5 scale.

The invariants that matter are that a crossed quote is removed whole rather than
adjusted, that no surviving value is rewritten, that `original_record_order`
survives so the mapping back to the source archive stays exact, and that the
receipt states plainly that this policy is lossy.
"""

from dataclasses import replace

from conftest import quotes
from factory.data.source_quarantine import (
    POLICY_VERSION,
    apply,
    fingerprint,
    is_crossed,
)


def _orders(rows):
    return [q.original_record_order for q in rows]


def test_clean_stream_is_untouched():
    rows = quotes([(1_000_000, 1_000_010)] * 50)
    kept, receipt = apply(rows)
    assert kept == rows
    assert receipt.crossed_removed == 0
    assert receipt.changed is False
    assert receipt.rows_in == receipt.rows_out == 50
    # The receipt must say this policy is lossy even when it removed nothing.
    assert receipt.receipt()["lossy"] is True


def test_crossed_quotes_are_removed_whole():
    rows = quotes(
        [
            (1_000_000, 1_000_010),
            (1_000_030, 1_000_020),  # crossed by 10
            (1_000_000, 1_000_010),
        ]
    )
    kept, receipt = apply(rows)
    assert _orders(kept) == [0, 2]
    assert receipt.crossed_removed == 1
    assert receipt.rows_in == 3 and receipt.rows_out == 2
    assert receipt.magnitude_units == {"10": 1}
    # The removed row is reported with enough to find it in the raw archive.
    assert receipt.first_positions[0]["original_record_order"] == 1
    assert receipt.first_positions[0]["crossing_units"] == 10


def test_no_value_is_rewritten():
    """A crossed quote is dropped, never adjusted to make it valid."""
    rows = quotes([(1_000_050, 1_000_040), (900_000, 900_010)])
    kept, _ = apply(rows)
    survivor = kept[0]
    assert (survivor.bid_int, survivor.ask_int) == (900_000, 900_010)
    assert survivor.original_record_order == 1


def test_equal_bid_and_ask_is_not_crossed():
    """bid == ask is a zero spread, which is unusual but not an arbitrage."""
    rows = quotes([(1_000_000, 1_000_000)])
    kept, receipt = apply(rows)
    assert kept == rows
    assert receipt.crossed_removed == 0


def test_is_crossed_predicate():
    assert is_crossed(quotes([(100, 90)])[0]) is True
    assert is_crossed(quotes([(90, 100)])[0]) is False
    assert is_crossed(quotes([(100, 100)])[0]) is False


def test_magnitude_histogram_is_recorded():
    rows = quotes(
        [
            (1_000_010, 1_000_000),  # 10
            (1_000_010, 1_000_000),  # 10
            (1_000_030, 1_000_000),  # 30
        ]
    )
    _, receipt = apply(rows)
    assert receipt.magnitude_units == {"10": 2, "30": 1}


def test_positions_are_bounded():
    """A partition with thousands of crossings must not emit thousands of rows."""
    rows = quotes([(1_000_010, 1_000_000)] * 500)
    _, receipt = apply(rows)
    assert receipt.crossed_removed == 500
    assert len(receipt.first_positions) == 20


def test_non_positive_quotes_are_not_this_policys_problem():
    """A zero price is a different defect; quarantine only removes crossings."""
    rows = quotes([(0, 10), (0, 0)])
    kept, receipt = apply(rows)
    assert kept == rows
    assert receipt.crossed_removed == 0


def test_record_order_survives_non_sequential_source_order():
    """Rows need not arrive in order; the policy must not depend on position."""
    rows = quotes([(1_000_000, 1_000_010)] * 5)
    rows[1] = replace(rows[1], bid_int=1_000_099, ask_int=1_000_000)
    rows[3] = replace(rows[3], bid_int=1_000_099, ask_int=1_000_000)
    kept, receipt = apply(rows)
    assert _orders(kept) == [0, 2, 4]
    assert receipt.crossed_removed == 2


def test_fingerprint_is_stable_and_content_bound():
    rows = quotes([(1_000_000, 1_000_010), (1_000_000, 1_000_020)])
    assert fingerprint(rows) == fingerprint(list(rows))
    assert fingerprint(rows) != fingerprint(rows[:1])
    assert len(fingerprint(rows)) == 64


def test_policy_version_is_declared():
    assert POLICY_VERSION == "source-quality-quarantine/v1"
