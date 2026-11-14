"""Versioned quarantine of provider quotes whose bid exceeds their ask.

A crossed quote is an arbitrage that cannot persist in a real market: the bid is
what a buyer will pay and the ask is what a seller demands, so ``bid > ask``
describes a state that cannot exist. It is a provider defect, not a market event.

Measured in USDCAD July 2026: 353 crossed quotes in 1,226,412 rows (0.029%), with
crossings of 1-7 pips at the provider's 1e5 scale. The magnitudes are small
because these are tick-rounding artifacts rather than large errors.

**This is a quarantine, not a correction.** Unlike
:mod:`factory.data.source_order`, which is lossless, removing a row loses the
observation. The trade-off is deliberate and recorded: failing the whole
partition would withhold 1,226,059 good rows because of 353 bad ones, whereas
quarantining the bad ones publishes the good ones and states exactly what was
removed and why.

Nothing is rewritten. A crossed quote is dropped whole; no price, timestamp,
scale or instrument field is adjusted, and `original_record_order` is preserved
on every retained row so the mapping back to the source archive stays exact. The
raw archive is never modified.

A clean partition passes through untouched with an empty receipt, so this policy
is inert unless the defect is actually measured.

The post-hoc scanner :mod:`factory.data.source_quality` independently reports
crossed quotes as ``INVALID_QUOTE``, so a quarantined partition remains visible
in QA rather than disappearing.
"""

from dataclasses import dataclass, field
import hashlib
import json

POLICY_VERSION = "source-quality-quarantine/v1"


@dataclass
class Quarantine:
    policy_version: str
    rows_in: int
    rows_out: int
    crossed_removed: int = 0
    magnitude_units: dict = field(default_factory=dict)
    first_positions: list = field(default_factory=list)
    uncorrectable: list = field(default_factory=list)

    @property
    def changed(self):
        return self.crossed_removed > 0

    def receipt(self):
        return {
            "policy_version": self.policy_version,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "crossed_quotes_removed": self.crossed_removed,
            "crossing_magnitude_units": self.magnitude_units,
            "first_removed_positions": self.first_positions,
            "lossy": True,
            "note": (
                "crossed quotes (bid > ask) are a provider defect and cannot "
                "persist in a real market; removed whole, no value rewritten"
            ),
        }


def is_crossed(q):
    """True when the quote's bid exceeds its ask."""
    return q.bid_int > q.ask_int


def apply(quotes):
    """Return (kept_quotes, Quarantine).

    Rows are inspected in the order given, so callers apply source-order
    correction first and quarantine second: the timeline is repaired, then
    unusable rows are removed from it.
    """
    receipt = Quarantine(policy_version=POLICY_VERSION, rows_in=len(quotes), rows_out=0)
    kept = []
    for q in quotes:
        if is_crossed(q):
            receipt.crossed_removed += 1
            magnitude = q.bid_int - q.ask_int
            key = str(magnitude)
            receipt.magnitude_units[key] = receipt.magnitude_units.get(key, 0) + 1
            if len(receipt.first_positions) < 20:
                receipt.first_positions.append(
                    {
                        "original_record_order": q.original_record_order,
                        "event_ts_utc_ns": q.event_ts_utc_ns,
                        "bid_int": q.bid_int,
                        "ask_int": q.ask_int,
                        "crossing_units": magnitude,
                    }
                )
            continue
        kept.append(q)
    receipt.rows_out = len(kept)
    # Defensive: nothing in `kept` can be crossed by construction, but a policy
    # that silently asserts its own correctness is how defects survive review.
    receipt.uncorrectable = [
        {"original_record_order": q.original_record_order} for q in kept if is_crossed(q)
    ]
    return kept, receipt


def fingerprint(quotes):
    """Content hash of the quarantined stream, for reproducible receipts."""
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
