"""Cached features are exactly the reference, never a second signal interpreter."""

from dataclasses import replace
import json

import pytest

from conftest import quotes
from factory.contracts import Signal
from factory.data import Catalog
from factory.features import closed_bar_events
from factory.features.disk import BarCache
from factory.strategies import iter_bar_signals, iter_signals


def dataset(tmp_path):
    cat = Catalog(tmp_path / "catalog")
    data = quotes(
        [(110000 + (i % 17) * 10, 110010 + (i % 17) * 10) for i in range(300)], step=30 * 10**9
    )
    # Sparse gap and source timestamp tie: preserve every row.
    data = [
        replace(q, event_ts_utc_ns=q.event_ts_utc_ns + (3600 * 10**9 if i >= 120 else 0))
        for i, q in enumerate(data)
    ]
    data[121] = replace(data[121], event_ts_utc_ns=data[120].event_ts_utc_ns)
    m = cat.commit(
        data,
        b"synthetic feature cache fixture",
        {"source": "synthetic test", "license": "test only", "synthetic": True},
    )
    return cat, m["dataset_hash"], data


@pytest.mark.parametrize("operator", ["momentum", "mean_reversion", "breakout"])
def test_exact_cached_events_signals_and_reuse(tmp_path, spec, operator):
    cat, key, data = dataset(tmp_path)
    cache = BarCache(tmp_path / "cache", batch_rows=2)
    spec = spec.model_copy(
        update={
            "signal": Signal(operator=operator, lookback=3, threshold="1"),
            "confirmations": ("M5", "H1"),
        }
    )
    frames = (spec.timeframe, *spec.confirmations)
    expected = list(closed_bar_events(data, frames))
    reference = list(iter_signals(data, spec))
    for _ in range(2):
        with cache.events(cat, key, "profile", "code-v1", frames) as events:
            assert list(events) == expected
        with cache.events(cat, key, "profile", "code-v1", frames) as events:
            assert list(iter_bar_signals(events, spec)) == reference
    assert cache.stats == {"misses": 3, "hits": 9, "evictions": 0, "quote_passes": 1}
    # Stops and signal parameters do not change the bars. Code/range changes do.
    with cache.events(
        cat, key, "profile", "code-v2", ("M1",), end_ns=data[150].event_ts_utc_ns
    ) as events:
        assert list(events) == list(closed_bar_events(data[:150], ("M1",)))
    assert cache.stats["quote_passes"] == 2


def test_restart_partial_build_and_eviction(tmp_path):
    cat, key, _ = dataset(tmp_path)
    root = tmp_path / "cache"
    cache = BarCache(root, max_entries=1)
    with cache.events(cat, key, "p", "a", ("M1",)) as events:
        list(events)
    entry = next(p for p in root.iterdir() if len(p.name) == 64)
    (entry / "manifest.json").unlink()  # interruption before manifest commit
    stale = root / ".building-killed"
    stale.mkdir()
    (stale / "uncommitted").write_bytes(b"incomplete")
    with cache.events(cat, key, "p", "a", ("M1",)) as events:
        assert list(events)
    assert not stale.exists()
    with cache.events(cat, key, "p", "b", ("M1",)) as events:
        assert list(events)
    assert cache.stats["evictions"] == 1
    assert len([p for p in root.iterdir() if len(p.name) == 64]) == 1


def test_corrupt_cache_source_and_overbudget_fail_closed(tmp_path):
    cat, key, _ = dataset(tmp_path)
    cache = BarCache(tmp_path / "cache")
    with cache.events(cat, key, "p", "a", ("M1",)) as events:
        list(events)
    entry = next(p for p in cache.root.iterdir() if len(p.name) == 64)
    with (entry / "bars.parquet").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        with cache.events(cat, key, "p", "a", ("M1",)):
            pass
    tiny = BarCache(tmp_path / "tiny", max_bytes=4096)
    with pytest.raises(ValueError, match="BAR_CACHE_BUDGET"):
        with tiny.events(cat, key, "p", "a", ("M1", "M5")):
            pass
    assert not list(tiny.root.glob("*/manifest.json"))
    manifest = json.loads((cat.root / key / "manifest.json").read_text())
    with (cat.root / key / "source.bin").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="CORRUPT_PARTITION"):
        with cache.events(cat, key, "p", "a", ("M1",)):
            pass
    assert manifest["rows"] == 300
