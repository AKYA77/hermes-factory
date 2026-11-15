"""Drive only fresh paused synthetic browser QA state through its actual coordinator."""

import argparse
from pathlib import Path
import json
import resource
import time

from apps.coordinator.service import cycle
from factory.data import atomic_bytes
from factory.experiments import Store
from factory.provenance import source_identity

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
qa = json.loads((args.state / "qa.json").read_text())
context = source_identity()
if (
    qa.get("scope") != "synthetic paused UI fixture; no historical metrics"
    or qa["source"] != context
):
    parser.error("fresh synthetic QA fixture with this exact source required")
store = Store(args.state / "factory.sqlite")
protocols = store.rows(
    "SELECT p.*,c.enabled FROM validation_protocols p JOIN validation_controls c USING(protocol_id)"
)
if len(protocols) != 1 or not protocols[0]["enabled"] or not store.paused():
    parser.error(
        "one enabled protocol in paused isolated QA state required; use browser --leave-enabled"
    )
if store.rows("SELECT * FROM validation_protocol_reports"):
    parser.error("a completed report already exists; inspect it without rerunning")
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
wall = time.perf_counter()
store.pause(False, "synthetic-browser-rehearsal")
try:
    reports = []
    for index in range(64):
        cycle(Store(args.state / "factory.sqlite"), args.state)
        reports = store.rows("SELECT * FROM validation_protocol_reports")
        if reports:
            break
    if len(reports) != 1:
        raise RuntimeError("No terminal native protocol report within QA cycle budget")
    value = json.loads(reports[0]["report_json"])
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        "status": value["status"],
        "protocol_id": value["protocol_id"],
        "protocol_purpose": value["protocol"]["purpose"],
        "artifact_hash": reports[0]["artifact_hash"],
        "source": context,
        "source_unchanged": context == source_identity(),
        "cycles": index + 1,
        "state_directory": args.state.name,
        "scope": "Actual supervised native synthetic software workflow; not historical/VPS/soak evidence",
        "wall_seconds": time.perf_counter() - wall,
        "children_cpu_seconds": after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
        "jobs": store.rows("SELECT state,count(*) count FROM jobs GROUP BY state"),
        "experiments": store.rows("SELECT count(*) count FROM experiments")[0]["count"],
        "evaluations": store.rows("SELECT count(*) count FROM evaluation_results")[0]["count"],
        "holdout_consumptions": store.rows("SELECT count(*) count FROM holdout_consumptions")[0][
            "count"
        ],
        "independently_validated": value["independently_validated"],
    }
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))
    if not report["source_unchanged"] or report["status"] == "FAILED_CHECKS":
        raise RuntimeError(value.get("reason", "Native QA report failed checks"))
finally:
    store.pause(True, "synthetic-browser-rehearsal-complete")
