"""Versioned, lossless correction of provider source-order defects.

Two distinct defects are observed in the acquired HistData archives. They have
different causes and require different corrections, and neither may be applied
silently.

1. **Exact duplicate block.** A contiguous run of rows repeats an earlier run
   verbatim: same timestamps, same prices, same source order. Measured in
   EURUSD October 2025: a 1,494-row block re-emitted byte-identically, which
   drives the timestamp backwards by ~3,598 s. The duplicate carries no
   information, so dropping it is lossless.

2. **Isolated out-of-order row.** A single row carries a timestamp earlier than
   its predecessor, typically by exactly one second. Measured in AUDUSD June
   2026: 10 such rows in 1,723,025. The provider's timestamp is the record of
   when the tick occurred; the file order is an assembly artifact. A stable sort
   by timestamp restores the timeline without altering any value.

Both corrections are order-only or duplicate-only. No timestamp, price, scale or
instrument field is ever rewritten, and `original_record_order` is preserved on
every retained row so the mapping back to the source archive stays exact. The
raw archive is never modified.

Anything this module cannot correct losslessly is left in place and reported, so
the caller can quarantine it.
"""

from dataclasses import dataclass, field
import hashlib
import json

POLICY_VERSION = "source-order-correction/v1"


@dataclass
class Correction:
    policy_version: str
    rows_in: int
    rows_out: int
    duplicate_blocks_removed: list = field(default_factory=list)
    rows_reordered: int = 0
    max_backward_step_ns: int = 0
    uncorrectable: list = field(default_factory=list)

    @property
    def changed(self):
        return bool(self.duplicate_blocks_removed or self.rows_reordered)

    def receipt(self):
        return {
            "policy_version": self.policy_version,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "duplicate_blocks_removed": self.duplicate_blocks_removed,
            "rows_reordered": self.rows_reordered,
            "max_backward_step_ns": self.max_backward_step_ns,
            "uncorrectable": self.uncorrectable,
        }


def _row_key(q):
    """Identity of a row for duplicate detection.

    Deliberately excludes `original_record_order`: two rows that agree on
    instrument, timestamp, bid, ask and scale are the same observed tick even if
    the provider wrote them at different positions.
    """
    return (
        q.instrument_id,
        q.event_ts_utc_ns,
        q.bid_int,
        q.ask_int,
        q.price_scale,
    )


def find_duplicate_blocks(quotes, min_block_rows=8, max_block_rows=100000):
    """Locate later blocks that repeat an earlier block verbatim.

    Returns a list of (start, end, original_start) with `end` exclusive, in file
    order. Only exact repeats are reported: a repeated timestamp with different
    prices is a genuine re-quote and must not be collapsed.

    A duplicate block always produces a backward timestamp jump at its start, so
    only those positions are candidates. That keeps this linear in the number of
    rows plus the number of defects, rather than quadratic in the partition size.
    """
    n = len(quotes)
    timestamps = [q.event_ts_utc_ns for q in quotes]
    # Candidate starts: the first row after a backward jump, plus position 0.
    candidates = [i for i in range(1, n) if timestamps[i] < timestamps[i - 1]]
    if timestamps and timestamps[0] > timestamps[1] if n > 1 else False:
        candidates.insert(0, 0)

    # Index earlier positions by row key so a candidate can be matched directly.
    index = {}
    for j, q in enumerate(quotes):
        index.setdefault(_row_key(q), []).append(j)

    blocks = []
    consumed = set()
    for start in candidates:
        if start in consumed:
            continue
        key = _row_key(quotes[start])
        best = None
        for original in index.get(key, ()):
            if original >= start:
                break
            if original in consumed:
                continue
            length = 0
            while (
                start + length < n
                and original + length < start
                and _row_key(quotes[start + length]) == _row_key(quotes[original + length])
                and length < max_block_rows
            ):
                length += 1
            if length >= min_block_rows and (best is None or length > best[1]):
                best = (original, length)
        if best is None:
            continue
        original, length = best
        blocks.append((start, start + length, original))
        consumed.update(range(start, start + length))
    blocks.sort()
    return blocks


def apply(quotes):
    """Return (corrected_quotes, Correction).

    Applies duplicate-block removal first, then a stable timestamp sort. The sort
    is stable so rows sharing a timestamp keep their source relative order.
    """
    receipt = Correction(policy_version=POLICY_VERSION, rows_in=len(quotes), rows_out=0)

    blocks = find_duplicate_blocks(quotes)
    dropped = set()
    for start, end, original in blocks:
        dropped.update(range(start, end))
        receipt.duplicate_blocks_removed.append(
            {
                "start_index": start,
                "end_index": end,
                "rows": end - start,
                "duplicates_block_at": original,
            }
        )
    kept = [q for i, q in enumerate(quotes) if i not in dropped]

    # A stable sort by timestamp. Rows already in order are untouched.
    ordered = sorted(kept, key=lambda q: q.event_ts_utc_ns)
    position = {id(q): i for i, q in enumerate(kept)}
    receipt.rows_reordered = sum(1 for i, q in enumerate(ordered) if position[id(q)] != i)

    previous = None
    for q in ordered:
        if previous is not None and q.event_ts_utc_ns < previous:
            receipt.max_backward_step_ns = max(
                receipt.max_backward_step_ns, previous - q.event_ts_utc_ns
            )
        previous = q.event_ts_utc_ns

    # Anything still out of order after a stable sort is impossible by
    # construction; report it defensively rather than asserting.
    residual = [
        {"order": q.original_record_order, "ts": q.event_ts_utc_ns}
        for i, q in enumerate(ordered)
        if i and ordered[i - 1].event_ts_utc_ns > q.event_ts_utc_ns
    ]
    receipt.uncorrectable = residual
    receipt.rows_out = len(ordered)
    return ordered, receipt


def fingerprint(quotes):
    """Content hash of the corrected stream, for reproducible receipts."""
    digest = hashlib.sha256()
    for q in quotes:
        digest.update(
            json.dumps(
                [
                    q.instrument_id,
                    q.event_ts_utc_ns,
                    q.bid_int,
                    q.ask_int,
                    q.price_scale,
                    q.original_record_order,
                ],
                separators=(",", ":"),
            ).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()
