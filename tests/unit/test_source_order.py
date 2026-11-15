"""Lossless correction of provider source-order defects.

Two defects are exercised: an exact duplicate block (measured in EURUSD October
2025, 1,494 rows re-emitted verbatim) and isolated out-of-order rows (measured in
AUDUSD June 2026, 10 rows one second behind their predecessor).

The invariants that matter are that no timestamp, price or scale is ever
rewritten, that `original_record_order` survives so the mapping back to the
source archive stays exact, and that a corrected stream is monotonic.
"""

from dataclasses import replace

from conftest import quotes
from factory.data.source_order import (
    POLICY_VERSION,
    apply,
    find_duplicate_blocks,
    fingerprint,
)


def _timestamps(rows):
    return [q.event_ts_utc_ns for q in rows]


def _assert_lossless(original, corrected, receipt):
    """No observed value may be invented or altered, and nothing is lost that the
    receipt does not account for.

    Rows removed as exact duplicates are expected; every other row must survive
    with its timestamp unchanged.
    """
    assert len(corrected) == receipt.rows_out
    removed = sum(b["rows"] for b in receipt.duplicate_blocks_removed)
    assert receipt.rows_in - removed == receipt.rows_out
    # Every retained row must still carry its original source position.
    assert {q.original_record_order for q in corrected} <= {
        q.original_record_order for q in original
    }
    # Every retained row's timestamp must appear in the source.
    source = {}
    for q in original:
        source.setdefault(q.event_ts_utc_ns, 0)
        source[q.event_ts_utc_ns] += 1
    for q in corrected:
        assert source.get(q.event_ts_utc_ns, 0) > 0
        source[q.event_ts_utc_ns] -= 1
    # The corrected stream must be monotonic.
    ts = _timestamps(corrected)
    assert all(b >= a for a, b in zip(ts, ts[1:]))


def test_exact_duplicate_block_is_removed_without_losing_information():
    base = quotes([(110000, 110010)] * 12, step=10**9)
    # Same timestamps and prices, but a distinct source position: a verbatim
    # re-emission, not a re-quote.
    duplicate = [replace(q, original_record_order=1000 + offset) for offset, q in enumerate(base)]
    original = base + duplicate

    blocks = find_duplicate_blocks(original)
    assert len(blocks) == 1
    start, end, at = blocks[0]
    assert (start, end, at) == (12, 24, 0)

    corrected, receipt = apply(original)
    assert receipt.policy_version == POLICY_VERSION
    assert receipt.rows_in == 24 and receipt.rows_out == 12
    assert receipt.duplicate_blocks_removed[0]["rows"] == 12
    assert receipt.rows_reordered == 0
    _assert_lossless(original, corrected, receipt)


def test_isolated_out_of_order_rows_are_reordered_by_timestamp():
    rows = quotes([(110000, 110010)] * 10, step=10**9)
    # Move one row one second backwards, as the provider did.
    original = list(rows)
    original[5] = replace(original[5], event_ts_utc_ns=rows[4].event_ts_utc_ns - 10**9)

    corrected, receipt = apply(original)
    assert receipt.duplicate_blocks_removed == []
    assert receipt.rows_reordered > 0
    assert receipt.rows_in == receipt.rows_out == 10
    assert receipt.uncorrectable == []
    _assert_lossless(original, corrected, receipt)


def test_a_repeated_timestamp_with_different_prices_is_not_collapsed():
    """A genuine re-quote is not a duplicate and must be preserved."""
    rows = quotes([(110000, 110010)] * 5, step=10**9)
    requote = [
        replace(q, event_ts_utc_ns=rows[offset].event_ts_utc_ns, original_record_order=100 + offset)
        for offset, q in enumerate(quotes([(110050, 110060)] * 5, step=10**9))
    ]
    original = rows + requote

    assert find_duplicate_blocks(original) == []
    corrected, receipt = apply(original)
    assert receipt.rows_out == 10
    assert receipt.duplicate_blocks_removed == []
    _assert_lossless(original, corrected, receipt)


def test_correction_is_deterministic_and_record_order_is_preserved():
    base = quotes([(110000, 110010)] * 12, step=10**9)
    duplicate = [replace(q, original_record_order=1000 + offset) for offset, q in enumerate(base)]
    original = base + duplicate

    first, receipt_a = apply(original)
    second, receipt_b = apply(original)
    assert fingerprint(first) == fingerprint(second)
    assert receipt_a.receipt() == receipt_b.receipt()
    # The duplicate's source positions are recorded, not silently discarded.
    assert receipt_a.duplicate_blocks_removed[0]["rows"] == 12


def test_clean_input_is_returned_unchanged():
    original = quotes([(110000, 110010)] * 16, step=10**9)
    corrected, receipt = apply(original)
    assert corrected == original
    assert receipt.changed is False
    assert fingerprint(corrected) == fingerprint(original)
