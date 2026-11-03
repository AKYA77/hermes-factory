"""Multi-period source identity, native tie ordering, censoring and reconstruction."""

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest
from conftest import quotes
from factory.data import Catalog
from factory.features import closed_bars
from factory.simulation.runner import replay, reconstruct_path
from factory.diagnostics import diagnose_trade


def leaf(cat, month, values, *, start=None, step=10**9):
    epoch = (
        int(datetime(2025, month, 1, tzinfo=timezone.utc).timestamp()) * 10**9
        if start is None
        else start
    )
    data = [
        replace(q, ingest_batch_id=f"synthetic-month-{month}")
        for q in quotes(values, start=epoch, step=step)
    ]
    m = cat.commit(
        data,
        f"synthetic month {month}".encode(),
        {
            "source": "project synthetic multi-period fixture",
            "license": "test only",
            "synthetic": True,
        },
    )
    return m, data


def test_multi_quarter_view_exact_rows_and_pruned_sequences(tmp_path):
    cat = Catalog(tmp_path)
    parts = []
    original = []
    for month in (1, 4, 7, 10):
        m, data = leaf(cat, month, [(110000 + i, 110010 + i) for i in range(4)])
        parts.append(m["dataset_hash"])
        original.extend(data)
    before = [(p, (tmp_path / p / "manifest.json").read_bytes()) for p in parts]
    view = cat.compose(parts)
    records = list(cat.read(view["dataset_hash"], batch_rows=1))
    assert [q.quote for q in records] == original
    assert [q.sequence for q in records] == list(range(16))
    assert [q.original_record_order for q in records] == list(range(4)) * 4
    subset = list(
        cat.read(
            view["dataset_hash"],
            start_ns=original[5].event_ts_utc_ns,
            end_ns=original[8].event_ts_utc_ns,
        )
    )
    assert [q.sequence for q in subset] == [5, 6, 7]
    assert cat.compose(parts)["dataset_hash"] == view["dataset_hash"]
    assert all((tmp_path / p / "manifest.json").read_bytes() == body for p, body in before)
    assert cat.verify(view["dataset_hash"], deep=True)["rows"] == 16


def test_boundary_tie_retains_both_original_records_and_forensics(tmp_path, profile, spec):
    cat = Catalog(tmp_path)
    a, qa = leaf(cat, 1, [(110000, 110010), (110000, 110010)])
    b, qb = leaf(cat, 2, [(110400, 110410), (112000, 112010)], start=qa[-1].event_ts_utc_ns)
    view = cat.compose([a["dataset_hash"], b["dataset_hash"]])
    records = list(cat.read(view["dataset_hash"]))
    assert records[1].event_ts_utc_ns == records[2].event_ts_utc_ns
    assert records[1].original_record_order == 1 and records[2].original_record_order == 0
    signals = [{"available_at": qa[0].event_ts_utc_ns, "side": "BUY"}]
    full = replay(iter(records), profile, spec, signals, True, batch_rows=1)
    compact = replay(
        cat.read(view["dataset_hash"]),
        profile,
        spec,
        signals,
        True,
        batch_rows=1,
        inline_paths=False,
        dataset_hash=view["dataset_hash"],
    )
    assert not compact["integrity_errors"]
    assert full["fills"] == compact["fills"]
    x, y = full["trades"][0], compact["trades"][0]
    assert diagnose_trade(x, profile.tick_size) == diagnose_trade(y, profile.tick_size)
    assert y["path_ref"]["version"] == "canonical-view-path/v1"
    assert list(reconstruct_path(cat, y, profile, True)) == x["path"]
    assert x["path"][-1]["source_ref"]["partition_hash"] == b["dataset_hash"]
    assert compact["fills"][-1]["source_ref"]["original_record_order"] == 0


def test_view_rejects_overlap_duplicates_mixed_instruments_and_tampering(tmp_path):
    cat = Catalog(tmp_path)
    a, qa = leaf(cat, 1, [(110000, 110010)] * 3)
    b, _ = leaf(cat, 2, [(110000, 110010)] * 3, start=qa[1].event_ts_utc_ns)
    with pytest.raises(ValueError, match="overlapping"):
        cat.compose([a["dataset_hash"], b["dataset_hash"]])
    with pytest.raises(ValueError, match="distinct"):
        cat.compose([a["dataset_hash"]] * 2)
    other = cat.commit(
        [replace(q, instrument_id="GBPUSD") for q in qa],
        b"other synthetic instrument",
        {"source": "fixture", "license": "test only", "synthetic": True},
    )
    with pytest.raises(ValueError, match="instrument/units/provider"):
        cat.compose([a["dataset_hash"], other["dataset_hash"]])
    view = cat.compose([a["dataset_hash"]])
    path = tmp_path / view["dataset_hash"] / "manifest.json"
    body = json.loads(path.read_text())
    body["rows"] += 1
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="view identity"):
        cat.verify(view["dataset_hash"])


def test_closed_bars_span_leaf_boundaries_without_future_publication(tmp_path):
    cat = Catalog(tmp_path)
    a, qa = leaf(cat, 1, [(110000, 110010)] * 3, step=30 * 10**9)
    b, _ = leaf(
        cat, 2, [(110300, 110310)] * 3, start=qa[-1].event_ts_utc_ns + 30 * 10**9, step=30 * 10**9
    )
    view = cat.compose([a["dataset_hash"], b["dataset_hash"]])
    bars = list(closed_bars(cat.read(view["dataset_hash"]), "M1"))
    flat = [
        replace(q.quote, original_record_order=q.sequence, ingest_batch_id="flat")
        for q in cat.read(view["dataset_hash"])
    ]
    assert bars == list(closed_bars(flat, "M1"))


@pytest.mark.parametrize("field", ["first_ns", "latest_verified_ns", "instrument"])
def test_leaf_metadata_cannot_hide_rows_or_change_instrument(tmp_path, field):
    cat = Catalog(tmp_path)
    m, _ = leaf(cat, 1, [(110000, 110010)] * 3)
    path = tmp_path / m["dataset_hash"] / "manifest.json"
    body = json.loads(path.read_text())
    body[field] = "GBPUSD" if field == "instrument" else body[field] + 1
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="metadata mismatch|bounds mismatch"):
        cat.verify(m["dataset_hash"])
