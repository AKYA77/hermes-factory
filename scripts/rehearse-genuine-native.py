"""Supervised native replay of a reviewed, retained genuine EURUSD source view.

This is a deliberately small integration rehearsal, not a validated strategy,
final unseen holdout, target-VPS benchmark or full end-to-end release gate.
"""

import argparse
from calendar import timegm
from collections import Counter
import hashlib
import json
from pathlib import Path
import resource
import time

from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, InstrumentSpec, Window, fingerprint, serialize
from factory.data import Catalog, atomic_bytes
from factory.data.admission import AdmissionSpec, InputRegistry, approved_policy
from factory.exploration.persistent import Search, SearchProtocol
from factory.provenance import execution_revision, source_identity
from factory.validation.access import record_use

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--qa", type=Path, required=True)
parser.add_argument("--review-notes", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
context = source_identity()
started, cpu = time.perf_counter(), time.process_time()
qa = json.loads(args.qa.read_text())
notes = json.loads(args.review_notes.read_text())
assert qa["source_context"] == context and qa["source_context_unchanged"]
quality = qa["quality"]
event_path = args.state / "artifacts" / "source-quality" / quality["run_id"] / "events.jsonl"
event_bytes = event_path.read_bytes()
events = [json.loads(x) for x in event_bytes.splitlines()]
assert hashlib.sha256(event_bytes).hexdigest() == notes["events_sha256"] == quality["events_sha256"]
assert dict(Counter(x["type"] for x in events)) == notes["event_counts"]
assert notes["acceptance_scope"] == "GENERIC_RESEARCH_REHEARSAL_ONLY_NOT_SOURCE_COMPLETENESS"
assert notes["unresolved_provider_gap_fidelity"] is True
registry = InputRegistry(args.state, Catalog(args.state / "catalog"))
profile = InstrumentSpec.model_validate(qa["profile"])
aid = registry.register_admission(
    AdmissionSpec(
        quality_run_id=quality["run_id"],
        profile_review_id=qa["profile_review_id"],
        calendar_review_id=qa["calendar_review_id"],
        accepted_events_sha256=quality["events_sha256"],
        window=Window.model_validate(qa["admission_window"]),
        reviewer=notes["reviewer"],
        reviewed_at_ns=notes["reviewed_at_ns"],
        source_acceptance_notes=serialize(notes),
        attestation="I reviewed all source QA events and accept this research input scope",
    )
)
manifest = registry.catalog.verify(qa["dataset_hash"])
# Original Jan/Feb view was already used for technical feature compilation.
# Preserve that fact in the isolated registry BEFORE any strategy is proposed.
with registry.store.transaction() as db:
    record_use(
        db,
        "EURUSD",
        "historical",
        qa["dataset_hash"],
        manifest["first_ns"],
        manifest["latest_verified_ns"] + 1,
        "prior-technical-feature-use",
        fingerprint({"prior_use": qa["prior_use"], "source_quality": quality["run_id"]}),
    )


def ns(month, day, hour):
    return timegm((2025, month, day, hour, 0, 0)) * 10**9


# Freeze the complete small rehearsal design before observing any strategy P&L.
design = dict(
    training=[ns(1, 8, 12), ns(1, 8, 16)],
    exploratory_oos=[ns(2, 5, 12), ns(2, 5, 16)],
    family="momentum",
    timeframe="M1",
    seed=42,
    max_trials=1,
    source_revision=execution_revision(),
    profile_hash=fingerprint(profile),
    admission_id=aid,
    independent_final_holdout=False,
    reasons=[
        "all Jan/Feb quotes had prior technical use",
        "one-unit generic research cap",
        "source gaps and broker feasibility remain uncertified",
    ],
)
design_path = args.state / "rehearsal-design.json"
if design_path.exists() and json.loads(design_path.read_text()) != design:
    raise ValueError("immutable rehearsal design differs")
atomic_bytes(design_path, (json.dumps(design, indent=2) + "\n").encode())
search = Search(registry.store, args.state)
p = SearchProtocol(
    schema_version="search/v4",
    admission_id=aid,
    research_kind="historical-training/v1",
    dataset_hash=qa["dataset_hash"],
    profile=profile,
    window=Window(start_ns=design["training"][0], end_ns=design["training"][1], role="train_only"),
    family=design["family"],
    timeframe=design["timeframe"],
    seed=design["seed"],
    max_trials=1,
    code_revision=design["source_revision"],
)
pid = search.register(p)
if not registry.store.rows("SELECT 1 FROM search_trials WHERE protocol_hash=?", (pid,)):
    search.ask(pid)
search.enqueue_pending()
registry.store.pause(False, "authorized-genuine-source-software-rehearsal")
cycle(registry.store, args.state, timeout=600)
search.feedback()
search.set_enabled(pid, False, actor="bounded-rehearsal")
training = registry.store.rows("SELECT * FROM experiments")
if len(training) != 1:
    raise ValueError(
        "native training failed: "
        + serialize(registry.store.rows("SELECT job_id,state,error FROM jobs"))
    )
training = training[0]
train_result = json.loads(training["result_json"])
strategy = json.loads(
    registry.store.rows(
        "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (training["strategy_id"],)
    )[0]["spec_json"]
)
contract = ExperimentContract.model_validate_json(training["contract_json"])
oos = ExperimentContract.model_validate(
    {
        **contract.model_dump(),
        "windows": [
            Window(
                start_ns=design["exploratory_oos"][0],
                end_ns=design["exploratory_oos"][1],
                role="selection_oos",
            )
        ],
        "evaluation_policy": approved_policy(
            aid, {"genuine-software-rehearsal": fingerprint(design), "stage": "exploratory_oos"}
        ),
    }
)
registry.store.enqueue(
    "validation",
    {
        "contract": oos.model_dump(mode="json"),
        "strategy": strategy,
        "profile": profile.model_dump(mode="json"),
    },
    oos.experiment_hash,
    actor="bounded-genuine-source-rehearsal",
    priority=1,
)
cycle(registry.store, args.state, timeout=600)
evaluations = registry.store.rows("SELECT * FROM evaluation_results")
if len(evaluations) != 1:
    raise ValueError(
        "native exploratory evaluation failed: "
        + serialize(registry.store.rows("SELECT job_id,state,error FROM jobs"))
    )
evaluation = json.loads(evaluations[0]["result_json"])
replays = [train_result, *[x["replay"] for x in evaluation["windows"]]]
assert not evaluation["synthetic"] and evaluation["status"] == "INSUFFICIENT_EVIDENCE"
assert not registry.store.rows("SELECT * FROM holdout_consumptions")
for r in replays:
    assert not r["synthetic"] and not r["integrity_errors"]
    assert r["reconciliation"]["native_reference_status"] == "VERIFIED"
assert source_identity() == context
registry.store.pause(True, "bounded-rehearsal-completed")
report = dict(
    status="PASS_BOUNDED_GENUINE_NATIVE_REHEARSAL",
    source_context=context,
    source_context_unchanged=True,
    design=design,
    design_sha256=fingerprint(design),
    dataset_hash=qa["dataset_hash"],
    source_rows=qa["rows"],
    admission_id=aid,
    training_run_id=training["run_id"],
    training_contract_hash=contract.experiment_hash,
    exploratory_contract_hash=oos.experiment_hash,
    evaluation_id=evaluations[0]["evaluation_id"],
    training_artifact_sha256=training["artifact_hash"],
    evaluation_artifact_sha256=evaluations[0]["artifact_hash"],
    results=[
        {
            "synthetic": r["synthetic"],
            "fills": len(r["fills"]),
            "closed_trades": len(r["trades"]),
            "signals_screened": r.get("signals_screened"),
            "ending_equity": r["ending_equity"],
            "reconciliation": r["reconciliation"],
        }
        for r in replays
    ],
    jobs=registry.store.rows("SELECT job_id,state,error,result FROM jobs"),
    parent_wall_seconds=time.perf_counter() - started,
    parent_cpu_seconds=time.process_time() - cpu,
    parent_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    children_cpu_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime
    + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
    cgroup_cpu_max=Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
    cgroup_memory_max=Path("/sys/fs/cgroup/memory.max").read_text().strip(),
    independent_market_validation=False,
    target_host_verified=False,
    SOFTWARE_VERIFIED=False,
    DATA_READY=False,
    OPERATION_READY=False,
)
atomic_bytes(args.output, (json.dumps(report, indent=2) + "\n").encode())
print(
    json.dumps(
        {
            k: report[k]
            for k in (
                "status",
                "training_run_id",
                "evaluation_id",
                "parent_wall_seconds",
                "children_cpu_seconds",
            )
        }
    )
)
