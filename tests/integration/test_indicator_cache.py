"""Exact shared primitives retain raw decisions, source identity and causality."""

from dataclasses import replace
from decimal import Decimal, localcontext
import json

import pytest

from conftest import quotes
from factory.contracts import TIMEFRAMES, Signal
from factory.data import Catalog
from factory.features.disk import BarCache
from factory.features.indicators import IndicatorCache
from factory.strategies import iter_bar_signals, iter_signals

OPERATORS = (
    "momentum",
    "mean_reversion",
    "breakout",
    "trend",
    "reversal",
    "range",
    "volatility",
    "session",
    "confluence",
)


def fixture(tmp_path, step=30 * 10**9):
    cat = Catalog(tmp_path / "catalog")
    data = quotes(
        [(110000 + ((i * 37) % 113) * 10, 110012 + ((i * 37) % 113) * 10) for i in range(180)],
        step=step,
    )
    data = [
        replace(q, event_ts_utc_ns=q.event_ts_utc_ns + (step * 13 if i >= 80 else 0))
        for i, q in enumerate(data)
    ]
    manifest = cat.commit(
        data,
        b"GENERATED indicator fixture",
        {"synthetic": True, "source": "test", "license": "test only"},
    )
    return cat, manifest["dataset_hash"], data


def signal(operator):
    return Signal(
        version="2",
        operator=operator,
        lookback=5,
        threshold=".5",
        components=("momentum", "trend") if operator == "confluence" else (),
        session_hours=tuple(range(24)) if operator == "session" else (),
    )


def cached(cache, bars, cat, dataset, spec, **kwargs):
    with cache.events(cat, dataset, "profile", "code", spec, bars, **kwargs) as (events, lookup):
        return list(iter_bar_signals(events, spec, transform_lookup=lookup))


@pytest.mark.parametrize("operator", OPERATORS)
@pytest.mark.parametrize("timeframe", TIMEFRAMES)
def test_all_categories_timeframes_exact_reuse_and_future_suffix(
    tmp_path, spec, operator, timeframe
):
    cat, dataset, data = fixture(tmp_path, TIMEFRAMES[timeframe] * 10**9 // 2)
    bars, cache = BarCache(tmp_path / "bars"), IndicatorCache(tmp_path / "indicators", batch_rows=7)
    spec = spec.model_copy(update={"signal": signal(operator), "timeframe": timeframe})
    expected = list(iter_signals(data, spec))
    assert cached(cache, bars, cat, dataset, spec) == expected
    old_stats = dict(cache.stats)
    changed = spec.model_copy(
        update={
            "stop_ticks": 200,
            "signal": spec.signal.model_copy(update={"threshold": Decimal("1.5")}),
        }
    )
    assert cached(cache, bars, cat, dataset, changed) == list(iter_signals(data, changed))
    assert cache.stats["bar_passes"] == old_stats["bar_passes"]
    assert cache.stats["hits"] > old_stats["hits"]
    end = data[110].event_ts_utc_ns
    prefix = cached(cache, bars, cat, dataset, spec, end_ns=end)
    assert prefix == [s for s in expected if s["available_at"] < end]


def test_decimal_context_identity_confirmation_and_failure_integrity(tmp_path, spec):
    cat, key, data = fixture(tmp_path)
    bars, cache = BarCache(tmp_path / "bars"), IndicatorCache(tmp_path / "indicators")
    spec = spec.model_copy(
        update={"signal": signal("mean_reversion"), "confirmations": ("M5", "H1")}
    )
    with localcontext() as ctx:
        ctx.prec = 12
        assert cached(cache, bars, cat, key, spec) == list(iter_signals(data, spec))
    misses = cache.stats["misses"]
    assert cached(cache, bars, cat, key, spec) == list(iter_signals(data, spec))
    assert cache.stats["misses"] == misses + 1
    with cache.events(cat, key, "profile", "code", spec, bars) as (events, lookup):
        with localcontext() as ctx:
            ctx.prec = 16
            with pytest.raises(ValueError, match="context changed"):
                list(iter_bar_signals(events, spec, transform_lookup=lookup))
    entry = next(
        p.parent
        for p in cache.root.glob("*/manifest.json")
        if json.loads(p.read_text())["inputs"]["decimal"]["prec"] == 28
    )
    with (entry / "values.parquet").open("ab") as f:
        f.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        cached(cache, bars, cat, key, spec)


def test_restart_eviction_budget_identity_and_canonical_change(tmp_path, spec):
    cat, key, data = fixture(tmp_path)
    bars = BarCache(tmp_path / "bars")
    root = tmp_path / "indicators"
    cache = IndicatorCache(root, max_entries=1)
    spec = spec.model_copy(update={"signal": signal("momentum")})
    expected = cached(cache, bars, cat, key, spec)
    entry = next(root.glob("*/manifest.json"))
    entry.unlink()
    stale = root / ".building-killed"
    stale.mkdir()
    (stale / "partial").write_bytes(b"partial")
    assert cached(cache, bars, cat, key, spec) == expected
    assert not stale.exists()
    cache = IndicatorCache(root, max_entries=1)
    with cache.events(cat, key, "changed-profile", "code", spec, bars) as (events, lookup):
        assert list(iter_bar_signals(events, spec, transform_lookup=lookup)) == expected
    assert cache.stats["evictions"] == 1
    with cache.events(cat, key, "changed-profile", "changed-code", spec, bars) as (events, lookup):
        assert list(iter_bar_signals(events, spec, transform_lookup=lookup)) == expected
    changed = spec.model_copy(update={"signal": spec.signal.model_copy(update={"lookback": 7})})
    assert cached(cache, bars, cat, key, changed) == list(iter_signals(data, changed))
    tiny = IndicatorCache(tmp_path / "tiny", max_bytes=4096)
    with pytest.raises(ValueError, match="BUDGET"):
        cached(tiny, bars, cat, key, spec)
    assert not list(tiny.root.glob("*/manifest.json"))
    with (cat.root / key / "source.bin").open("ab") as f:
        f.write(b"changed source")
    with pytest.raises(ValueError, match="CORRUPT_PARTITION"):
        cached(cache, bars, cat, key, spec)


@pytest.mark.parametrize("operator", ("mean_reversion", "trend"))
def test_native_training_screen_and_evaluation_use_identical_cached_primitives(
    tmp_path, monkeypatch, operator
):
    from apps.coordinator import worker
    from factory.features import indicators
    from factory.operations.fixtures import seed
    from factory.screening import SCREEN_POLICY
    from factory.contracts import StrategySpec
    from factory.validation.evaluate import evaluate

    payload = seed(tmp_path, 240)
    spec = StrategySpec.model_validate(payload["strategy"]).model_copy(
        update={
            "signal": Signal(
                version="2",
                operator=operator,
                lookback=64,
                threshold=".01" if operator == "trend" else ".5",
            )
        }
    )
    payload["strategy"] = spec.model_dump(mode="json")
    payload["contract"]["strategy_hash"] = spec.strategy_hash
    payload["screening"] = SCREEN_POLICY
    first = worker.run(payload, tmp_path)
    assert first["result"]["fills"] and first["result"]["signals_screened"]
    assert not first["result"]["integrity_errors"]
    manifests = list((tmp_path / "cache" / "indicators").glob("*/manifest.json"))
    assert manifests
    cached_bytes = {p: p.read_bytes() for p in manifests}
    monkeypatch.setattr(indicators, "use_indicator_cache", lambda spec: False)
    assert worker.run(payload, tmp_path) == first
    assert all(p.read_bytes() == content for p, content in cached_bytes.items())
    # Frozen evaluation must be disjoint from consumed training. A separate
    # independent state uses this generated fixture solely for its OOS role.
    evaluation_root = tmp_path / "evaluation-state"
    ep = seed(evaluation_root, 240)
    ep["strategy"] = spec.model_dump(mode="json")
    ep["contract"]["strategy_hash"] = spec.strategy_hash
    ep["contract"]["windows"][0]["role"] = "selection_oos"
    ep["contract"]["evaluation_policy"] = "synthetic-evaluation/v1"
    monkeypatch.undo()
    cached_result = evaluate(evaluation_root / "catalog", ep)
    assert list((evaluation_root / "cache" / "indicators").glob("*/manifest.json"))
    monkeypatch.setattr(indicators, "use_indicator_cache", lambda spec: False)
    assert evaluate(evaluation_root / "catalog", ep) == cached_result


def test_sigkill_before_manifest_recovers_identical_feature_entry(tmp_path, spec):
    import subprocess
    import sys

    cat, key, data = fixture(tmp_path)
    spec = spec.model_copy(update={"signal": signal("mean_reversion")})
    payload = tmp_path / "request.json"
    payload.write_text(json.dumps({"dataset": key, "spec": spec.model_dump(mode="json")}))
    code = """
import json,os,signal,sys
from pathlib import Path
from factory.contracts import StrategySpec
from factory.data import Catalog
from factory.features.disk import BarCache
from factory.features.indicators import IndicatorCache
import factory.features.indicators as module
root=Path(sys.argv[1]); request=json.loads((root/'request.json').read_text())
module.atomic_bytes=lambda *a,**kw:os.kill(os.getpid(),signal.SIGKILL)
with IndicatorCache(root/'indicators').events(Catalog(root/'catalog'),request['dataset'],'profile','code',StrategySpec.model_validate(request['spec']),BarCache(root/'bars')):
    raise AssertionError('manifest unexpectedly published')
"""
    killed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], timeout=20, capture_output=True
    )
    assert killed.returncode == -9, killed.stderr.decode()
    root = tmp_path / "indicators"
    assert list(root.glob("*/values.parquet")) and not list(root.glob("*/manifest.json"))
    cache, bars = IndicatorCache(root), BarCache(tmp_path / "bars")
    expected = list(iter_signals(data, spec))
    assert cached(cache, bars, cat, key, spec) == expected
    assert cached(IndicatorCache(root), bars, cat, key, spec) == expected
    assert len(list(root.glob("*/manifest.json"))) == 1
    assert not list(root.glob(".building-*"))


def test_bar_cache_identity_covers_code_and_fill_version(tmp_path):
    cat, dataset, _ = fixture(tmp_path)
    cache = BarCache(tmp_path / "bars")
    with cache.events(
        cat, dataset, "profile", "rev", ("M1",), code_revision="code-a", fill_version="fill-1"
    ) as stream:
        first = list(stream)
    assert cache.stats["misses"] == 1
    # An exact rerun reuses the cached bars.
    with cache.events(
        cat, dataset, "profile", "rev", ("M1",), code_revision="code-a", fill_version="fill-1"
    ) as stream:
        assert list(stream) == first
    assert cache.stats["hits"] == 1
    # A code version change invalidates the cache.
    with cache.events(
        cat, dataset, "profile", "rev", ("M1",), code_revision="code-b", fill_version="fill-1"
    ) as stream:
        assert list(stream) == first
    assert cache.stats["misses"] == 2
    # A fill version change invalidates the cache.
    with cache.events(
        cat, dataset, "profile", "rev", ("M1",), code_revision="code-b", fill_version="fill-2"
    ) as stream:
        assert list(stream) == first
    assert cache.stats["misses"] == 3
    # A data revision change invalidates the cache.
    with cache.events(
        cat, dataset, "profile", "rev2", ("M1",), code_revision="code-b", fill_version="fill-2"
    ) as stream:
        assert list(stream) == first
    assert cache.stats["misses"] == 4
