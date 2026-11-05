#!/usr/bin/env python3
"""Scan preserved real source partitions; no market strategy or broker approval."""

import argparse
from pathlib import Path
import hashlib
import json
import resource
import time

from factory.data import Catalog, atomic_bytes
from factory.data.source_quality import SourceQuality, SourceQualityPolicy
from factory.provenance import source_identity

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--catalog", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--policy", type=Path, default=Path("config/source-quality-policy.example.json")
)
args = parser.parse_args()
if args.state.exists():
    parser.error("new isolated state required")
policy = SourceQualityPolicy.model_validate_json(args.policy.read_text())
catalog = Catalog(args.catalog)
identities = sorted(path.parent.name for path in args.catalog.glob("*/manifest.json"))
if not identities:
    parser.error("preserved source partitions required")
context = source_identity()
started = time.perf_counter()
usage = resource.getrusage(resource.RUSAGE_SELF)
service = SourceQuality(args.state, catalog)
results = []
for identity in identities:
    manifest = catalog.verify(identity)
    if manifest["provenance"].get("synthetic") or manifest["schema_version"] != "data/v2":
        parser.error("this probe requires preserved historical v2 leaf partitions")
    result = service.run(identity, policy)
    measured = json.loads(
        service.store.rows(
            "SELECT resources_json FROM source_quality_attempts WHERE run_id=? ORDER BY created_at DESC",
            (result["run_id"],),
        )[0]["resources_json"]
    )
    passed = (
        result["complete_source_scan"]
        and result["source_structural_status"] == "PASS"
        and result["counts"]["rows_scanned"] == manifest["rows"]
        and not result["historical_admission"]
    )
    results.append(
        {
            "instrument": manifest["instrument"],
            "dataset_hash": identity,
            "quality_run_id": result["run_id"],
            "rows": result["counts"]["rows_scanned"],
            "counts": result["counts"],
            "events_sha256": result["events_sha256"],
            "events_bytes": result["events_bytes"],
            "calendar_status": result["calendar_status"],
            "profile_status": result["profile_status"],
            "requested_period_status": result["requested_period_status"],
            "passed_technical_scan": passed,
            "resources": measured,
        }
    )
    print(
        manifest["instrument"]
        + ": "
        + str(result["counts"]["rows_scanned"])
        + " exact rows scanned",
        flush=True,
    )
    if not passed:
        raise RuntimeError("Source quality technical failure: " + result["run_id"])
after = resource.getrusage(resource.RUSAGE_SELF)
report = {
    "status": "PASS_STRUCTURAL_STREAM_QA_METADATA_BLOCKED",
    "source_context": context,
    "source_unchanged": context == source_identity(),
    "scope": "full-row real January canonical-source integrity/gap processing; not a historical strategy backtest or verified calendar/broker profile",
    "results": results,
    "total_rows": sum(r["rows"] for r in results),
    "wall_seconds": time.perf_counter() - started,
    "cpu_seconds": after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
    "process_peak_rss_bytes": after.ru_maxrss * 1024,
    "disk_state_bytes": sum(p.stat().st_size for p in args.state.rglob("*") if p.is_file()),
    "cgroup_cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
    "cgroup_memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "software_verified": False,
    "data_ready": False,
    "operation_ready": False,
    "warnings": [
        "Page cache uncontrolled",
        "No forced-8GB or target-Contabo proof",
        "Existing captures, not a fresh download/import benchmark",
        "All gap/event artifacts retained locally; this summary omits provider quote values",
        "Unknown broker/calendar facts do not become verified through scanning",
    ],
}
atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
print(json.dumps({k: v for k, v in report.items() if k != "results"}), flush=True)
if not report["source_unchanged"]:
    raise SystemExit("Source changed during benchmark")
