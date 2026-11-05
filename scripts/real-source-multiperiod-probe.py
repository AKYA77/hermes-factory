"""Actual retained January/February source pipeline; never strategy validation."""
import argparse
from calendar import timegm
import hashlib
import json
from pathlib import Path
import resource
import time

from factory.contracts import fingerprint, serialize
from factory.data import Catalog, atomic_bytes
from factory.data.versions import SourceSlot, SourceVersions
from factory.features.disk import BarCache
from factory.operations.backfill_history import run as backfill_report
from factory.provenance import execution_revision, source_identity
from factory.validation.access import record_use

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--catalog", type=Path, required=True)
parser.add_argument("--archives", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
context = source_identity()
started, cpu = time.perf_counter(), time.process_time()
catalog = Catalog(args.catalog)
versions = SourceVersions(args.state, catalog)
receipts = [json.loads((args.catalog / f"EURUSD-2025{month:02}-import-report.json").read_text())
            for month in (1, 2)]
slots, observations = [], []
for month, receipt in enumerate(receipts, start=1):
    assert receipt["status"] == "STRUCTURAL_IMPORT_PASS"
    if "source_context_unchanged" in receipt:
        assert receipt["source_context_unchanged"] is True
    manifest = catalog.verify(receipt["dataset"]["dataset_hash"])
    assert manifest["instrument"] == "EURUSD" and not manifest["provenance"].get("synthetic")
    scope = SourceSlot(source_id=manifest["source_id"], instrument="EURUSD", synthetic=False,
                       start_ns=(timegm((2025, month, 1, 0, 0, 0)) + 5 * 3600) * 10**9,
                       end_ns=(timegm((2025, month + 1, 1, 0, 0, 0)) + 5 * 3600) * 10**9)
    observed = versions.observe(scope, manifest["dataset_hash"], actor="real-source-software-rehearsal")
    current = versions.current(scope)
    if current is None:
        versions.select(observed, actor="real-source-software-rehearsal",
                        reason="isolated source fidelity test only; not metadata or strategy approval")
    elif current["observation_id"] != observed:
        raise ValueError("rehearsal will not overwrite another selected source revision")
    slots.append(scope)
    observations.append({"observation_id": observed, "dataset_hash": manifest["dataset_hash"],
                         "rows": manifest["rows"], "source_sha256": manifest["source_sha256"],
                         "original_import_source_context": receipt.get("source_context", "NOT_CAPTURED_IN_LEGACY_IMPORT_RECEIPT; independently verified now"),
                         "quote_stream_sha256": manifest["quote_stream_sha256"]})
snapshot = versions.snapshot(slots)
manifest = catalog.verify(snapshot["dataset_hash"])
assert manifest["rows"] == sum(v["rows"] for v in observations)
source_stage = {"wall_seconds": time.perf_counter() - started, "cpu_seconds": time.process_time() - cpu}
# Conservatively retain technical use so these periods are never later declared
# wholly untouched in this managed state. No optimizer/strategy outcome is used.
with versions.store.transaction() as db:
    record_use(db, "EURUSD", "historical", manifest["dataset_hash"], manifest["first_ns"],
               manifest["latest_verified_ns"] + 1, "software-feature-rehearsal",
               fingerprint({"snapshot": snapshot, "revision": execution_revision()}))
cache = BarCache(args.state / "cache" / "bars")
unit_key = fingerprint({"instrument": "EURUSD", "scope": "midpoint source software only; UNKNOWN_SPEC"})
feature_start, feature_cpu = time.perf_counter(), time.process_time()
boundary = receipts[1]["dataset"]["first_ns"]

def consume():
    digest = hashlib.sha256()
    counts, delayed = {"M1": 0, "H1": 0}, []
    with cache.events(catalog, manifest["dataset_hash"], unit_key, execution_revision(), ("M1", "H1")) as events:
        for event in events:
            digest.update(serialize({tf: vars(bar) for tf, bar in event.items()}).encode() + b"\n")
            for tf, bar in event.items():
                counts[tf] += 1
                assert bar.available_at >= bar.end_ns
                if bar.end_ns < slots[0].end_ns and bar.available_at >= boundary and len(delayed) < 10:
                    delayed.append({"timeframe": tf, "end_ns": str(bar.end_ns),
                                    "available_at_ns": str(bar.available_at)})
    return {"sha256": digest.hexdigest(), "counts": counts, "cross_month_publication": delayed}

cold = consume()
cold_metrics = {"wall_seconds": time.perf_counter() - feature_start,
                "cpu_seconds": time.process_time() - feature_cpu}
warm_start, warm_cpu = time.perf_counter(), time.process_time()
warm = consume()
assert warm == cold and cold["cross_month_publication"]
warm_metrics = {"wall_seconds": time.perf_counter() - warm_start,
                "cpu_seconds": time.process_time() - warm_cpu}
coverage = backfill_report("2026-11", args.archives, args.catalog, args.state / "backfill-status.json",
                           execute=False)
assert coverage["source_context_unchanged"]
report = {
    "status": "PASS_SOURCE_SELECTION_VIEW_AND_EXACT_CLOSED_FEATURES",
    "scope": "genuine historical source pipeline only; NOT native strategy evaluation, scientific validation or full C2",
    "source_context": context, "source_context_unchanged": source_identity() == context,
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "source_stage": source_stage, "observations": observations, "snapshot": snapshot,
    "total_quotes": manifest["rows"], "closed_features": cold,
    "first_build_metrics": cold_metrics, "cache_reuse_metrics": warm_metrics,
    "cache_stats": cache.stats,
    "coverage": {k: coverage[k] for k in ("requested_partitions", "structurally_imported_partitions", "remaining_partitions", "new_partition_attempts")},
    "wall_seconds": time.perf_counter() - started, "cpu_seconds": time.process_time() - cpu,
    "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    "state_disk_bytes": sum(p.stat().st_size for p in args.state.rglob('*') if p.is_file()),
    "cgroup_cpu_max": Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
    "cgroup_memory_max": Path('/sys/fs/cgroup/memory.max').read_text().strip(),
    "page_cache": "uncontrolled; first build is not an OS cold-cache claim",
    "historical_strategy_evaluation": False, "instrument_profile_status": "UNKNOWN_SPEC",
    "SOFTWARE_VERIFIED": False, "DATA_READY": False, "OPERATION_READY": False,
}
assert report["source_context_unchanged"]
atomic_bytes(args.output, (json.dumps(report, indent=2) + '\n').encode())
print(json.dumps({k:report[k] for k in ('status','total_quotes','wall_seconds','cpu_seconds','process_peak_rss_bytes')}))
