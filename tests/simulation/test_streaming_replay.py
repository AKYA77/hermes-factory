"""Native stream parity, causal boundaries and independently reconciled cash."""

from dataclasses import replace
from decimal import Decimal as D
import pytest

from conftest import quotes
from factory.diagnostics import diagnose_trade
from factory.simulation.runner import replay
from factory.simulation.streaming import QuoteSpool
from test_partial_engine import PartialBook
from nautilus_trader.model.enums import OrderType


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("batch_rows", [1, 2, 3, 8192])
def test_native_iterator_matches_materialized_ties_gaps(profile, spec, side, batch_rows):
    q = quotes(
        [(110000, 110010), (110000, 110010), (110100, 110110), (110400, 110410), (109000, 109010)]
    )
    q[3] = replace(q[3], event_ts_utc_ns=q[2].event_ts_utc_ns)
    signals = [{"available_at": q[0].event_ts_utc_ns, "side": side}]
    reference = replay(q, profile, spec, signals, True, _materialized_reference=True)
    streamed = replay(iter(q), profile, spec, iter(signals), True, batch_rows=batch_rows)
    assert streamed == reference
    assert not streamed["reconciliation"]["issues"]
    assert streamed["reconciliation"]["native_fill_count"] == len(streamed["fills"])


@pytest.mark.parametrize("side", ["BUY", "SELL"])
@pytest.mark.parametrize("partial", [False, True])
def test_compact_path_preserves_diagnostics(profile, spec, side, partial):
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410), (109000, 109010)])
    sig = [{"available_at": q[0].event_ts_utc_ns, "side": side}]

    def run(compact):
        return replay(
            iter(q),
            profile,
            spec,
            sig,
            True,
            batch_rows=1,
            fill_model=PartialBook(profile, OrderType.MARKET) if partial else None,
            inline_paths=not compact,
            dataset_hash="d" * 64,
        )

    a, b = run(False), run(True)
    for x, y in zip(a["trades"], b["trades"], strict=True):
        assert diagnose_trade(x, profile.tick_size) == diagnose_trade(y, profile.tick_size)
        assert "path" not in y
        assert y["path_ref"]["first_source_record_order"] == x["path"][0]["source_record_order"]
        assert y["path_ref"]["last_source_record_order"] == x["path"][-1]["source_record_order"]
    assert a["fills"] == b["fills"]


def test_no_fill_on_information_quote_or_its_timestamp_ties(profile, spec):
    q = quotes([(110000, 110010)] * 4)
    q[1] = replace(q[1], event_ts_utc_ns=q[0].event_ts_utc_ns)
    q[2] = replace(q[2], event_ts_utc_ns=q[0].event_ts_utc_ns)
    r = replay(
        q,
        profile,
        spec,
        [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}],
        True,
        batch_rows=1,
    )
    assert r["fills"][0]["ts"] == q[3].event_ts_utc_ns
    assert r["fills"][0]["quote_index"] == 3
    assert not r["reconciliation"]["issues"]


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_unavailable_exit_and_timeout_stream_parity(profile, spec, side):
    sig = [{"available_at": 1735689600 * 10**9, "side": side}]
    for step in [10**9, 86400 * 10**9, 90000 * 10**9]:
        q = quotes([(110000, 110010)] * 3, step=step)
        a = replay(q, profile, spec, sig, True, _materialized_reference=True)
        b = replay(iter(q), profile, spec, sig, True, batch_rows=1)
        assert a == b
        assert not b["reconciliation"]["issues"]


def test_native_rounding_difference_is_explicit(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110400, 110410)])
    r = replay(q, profile, spec, [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}], True)
    ledger = r["reconciliation"]
    assert ledger["native_minus_exact_equity"] == str(
        D(ledger["native_balance"]) - D(r["ending_equity"])
    )
    assert ledger["currency_rounding_status"] == "DIFFERENCE_REQUIRES_POLICY"
    assert not ledger["issues"]
    cash = sum(
        (
            (1 if f["side"] == "SELL" else -1) * D(f["size"]) * D(f["price"]) - D(f["commission"])
            for f in r["fills"]
        ),
        D(0),
    )
    assert D(r["ending_equity"]) == D(20) + cash


def test_spool_rejects_off_grid_and_duplicate_sequence(profile):
    q = quotes([(110000, 110010)])
    with QuoteSpool(iter(q), profile) as spool:
        assert spool.count == 1 and spool.row(0)[1:3] == (110000, 110010)
    with pytest.raises(ValueError, match="invalid quote"):
        QuoteSpool(q + q, profile)
    finer = replace(q[0], price_scale=1000000, bid_int=1100001, ask_int=1100011)
    p = profile.model_copy(update={"price_scale": 1000000})
    with pytest.raises(ValueError, match="grid"):
        QuoteSpool([finer], p)


def test_spool_and_result_capacity_fail_explicitly(profile):
    from factory.simulation.streaming import BoundedRecords, RECORD

    with pytest.raises(ValueError, match="REPLAY_SPOOL_BUDGET"):
        QuoteSpool(iter(quotes([(110000, 110010)] * 3)), profile, max_bytes=RECORD.size * 2)
    records = BoundedRecords(1)
    records.append("preserved")
    with pytest.raises(ValueError, match="REPLAY_RESULT_BUDGET"):
        records.append("overflow")
    assert records == ["preserved"]


def test_reconstruct_compact_forensic_reference(tmp_path, profile, spec):
    from factory.data import Catalog
    from factory.simulation.runner import reconstruct_path

    data = quotes([(110000, 110010)] * 2 + [(110100, 110110), (110400, 110410), (110500, 110510)])
    cat = Catalog(tmp_path)
    manifest = cat.commit(
        data,
        b"test fixture",
        {"source": "synthetic", "license": "project synthetic", "synthetic": True},
    )
    signals = [{"available_at": data[0].event_ts_utc_ns, "side": "BUY"}]
    a = replay(data, profile, spec, signals, True)
    b = replay(
        iter(data),
        profile,
        spec,
        signals,
        True,
        inline_paths=False,
        dataset_hash=manifest["dataset_hash"],
    )
    assert list(reconstruct_path(cat, b["trades"][0], profile, True)) == a["trades"][0]["path"]
