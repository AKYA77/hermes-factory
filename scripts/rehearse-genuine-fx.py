"""Bounded genuine-source QA/native rehearsal; never independent validation.

Use retained HistData January/February EURUSD imports. No downloads, quote
mutation, Gold convention, broker-spec claim, or validated promotion.
"""

import argparse
from calendar import timegm
import hashlib
import json
import os
from pathlib import Path
import resource
import time

from factory.contracts import Window
from factory.data import Catalog, atomic_bytes
from factory.data.admission import (
    InputRegistry,
    ReferenceReview,
    Citation,
    PROFILE_FIELDS,
    CALENDAR_FIELDS,
)
from factory.data.source_quality import SourceQuality, SourceQualityPolicy
from factory.instruments.calendar import CalendarSpec, SessionCalendar
from factory.instruments.research_profiles import generic_fx_profile, verified_fx_captures
from factory.provenance import source_identity

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
parser.add_argument("--catalog", type=Path, required=True)
parser.add_argument("--references", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
context = source_identity()
started, cpu = time.perf_counter(), time.process_time()
references = verified_fx_captures(args.references)
model_doc = Path("docs/reference-profiles/generic-fx-base-unit-unlevered-cap1-v1.md").read_bytes()
model_sha = hashlib.sha256(model_doc).hexdigest()
source, target = Catalog(args.catalog), Catalog(args.state / "catalog")
leaves = []
for month in (1, 2):
    receipt = json.loads((args.catalog / f"EURUSD-2025{month:02}-import-report.json").read_text())
    identity = receipt["dataset"]["dataset_hash"]
    manifest = source.verify(identity, deep=True)
    assert manifest["instrument"] == "EURUSD" and not manifest["provenance"]["synthetic"]
    assert manifest["price_scale"] == 1_000_000
    assert manifest["observed_price_quantum"] == "0.00001"
    dest = target.root / identity
    dest.mkdir(exist_ok=True)
    for name in ("manifest.json", "source.bin", "quotes.parquet"):
        src, dst = source.root / identity / name, dest / name
        if not dst.exists():
            os.link(src, dst)  # immutable bytes; never alter either catalog's leaves
        if name == "manifest.json" and src.read_bytes() != dst.read_bytes():
            raise ValueError("existing manifest differs")
    target.verify(identity, deep=True)
    leaves.append(identity)
view = target.compose(leaves)
start = (timegm((2025, 1, 1, 0, 0, 0)) + 5 * 3600) * 10**9
end = (timegm((2025, 3, 1, 0, 0, 0)) + 5 * 3600) * 10**9
profile = generic_fx_profile("EURUSD", 1_000_000, ".00001")
tzif = Path("/usr/share/zoneinfo/America/New_York").read_bytes()
calendar = CalendarSpec(
    instrument="EURUSD",
    version="generic-envelope-not-broker/v1",
    timezone="America/New_York",
    tzif_sha256=hashlib.sha256(tzif).hexdigest(),
    source_document_sha256=model_sha,
    source_citation="Declared generic Sunday17:00-Friday17:00 NY envelope, NOT OANDA17:05/16:59 or HistData maintenance/holiday facts",
    effective_start_ns=start,
    effective_end_ns=end,
    weekly_sessions=({"start_second": 6 * 86400 + 17 * 3600, "end_second": 4 * 86400 + 17 * 3600},),
    closures=(),
    ambiguous_boundary="reject",
)
registry = InputRegistry(args.state, target)
common = dict(
    effective_start_ns=start,
    effective_end_ns=end,
    reviewed_at_ns=time.time_ns(),
    reviewer="authorized initial builder: generic research assumptions; no broker feasibility certification",
    attestation="I reviewed the captured references and their dated research scope",
)


def cite(name, locator, interpretation, basis="published_reference"):
    receipt = references["receipts"][name]
    return Citation(
        document_sha256=receipt["sha256"],
        source=receipt["resolved_url"],
        locator=locator,
        interpretation=interpretation,
        basis=basis,
    )


assumption = Citation(
    document_sha256=model_sha,
    source="project generic research model/v1",
    locator="Declared model assumptions and applicability dates",
    interpretation="Explicit research choice only; no broker-account fact or retrospective broker certification",
    basis="explicit_research_assumption",
)
citations = {k: assumption for k in PROFILE_FIELDS}
citations["pip_size"] = cite(
    "oanda-pip",
    "EUR/USD 1.1600 to1.1605 =0.0005 =5pip; JPY .01",
    "Published ordinary FX pip convention; not inferred from quote digits",
)
for k in ("base_currency", "quote_currency"):
    citations[k] = cite(
        "iso4217-list", "Ccy EUR and USD", "ISO currency identities, no broker contract inference"
    )
documents = {model_sha: model_doc}
for c in citations.values():
    for name, r in references["receipts"].items():
        if r["sha256"] == c.document_sha256:
            documents[r["sha256"]] = references["captures"][name]
pid = registry.register_reference(
    ReferenceReview(profile=profile, citations=citations, **common), documents
)
cid = registry.register_reference(
    ReferenceReview(
        calendar=calendar, citations={k: assumption for k in CALENDAR_FIELDS}, **common
    ),
    {model_sha: model_doc},
    tzif=tzif,
)
qa = SourceQuality(args.state, target).run(
    view["dataset_hash"],
    SourceQualityPolicy(
        gap_threshold_ns=60 * 10**9,
        unchanged_threshold_ns=600 * 10**9,
        timestamp_quantum_ns=10**6,
        max_examples=10,
        max_events_bytes=64 * 1024**2,
        expected_start_ns=start,
        expected_end_ns=end,
    ),
    profile=profile,
    calendar=SessionCalendar(calendar, tzif),
)
report = dict(
    status="SOURCE_QA_AWAITING_ALL_EVENT_REVIEW",
    source_context=context,
    source_context_unchanged=source_identity() == context,
    dataset_hash=view["dataset_hash"],
    leaves=leaves,
    rows=view["rows"],
    profile=profile.model_dump(mode="json"),
    profile_review_id=pid,
    calendar_review_id=cid,
    quality=qa,
    admission_window=Window(start_ns=start, end_ns=end, role="train_only").model_dump(),
    retrieved_references=references["receipts"],
    prior_use="January/February technical feature access already recorded; no unseen holdout claim",
    wall_seconds=time.perf_counter() - started,
    cpu_seconds=time.process_time() - cpu,
    process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    cgroup_cpu_max=Path("/sys/fs/cgroup/cpu.max").read_text().strip(),
    cgroup_memory_max=Path("/sys/fs/cgroup/memory.max").read_text().strip(),
    SOFTWARE_VERIFIED=False,
    DATA_READY=False,
    OPERATION_READY=False,
)
assert report["source_context_unchanged"]
atomic_bytes(args.output, (json.dumps(report, indent=2) + "\n").encode())
print(
    json.dumps(
        {
            k: report[k]
            for k in ("status", "rows", "wall_seconds", "cpu_seconds", "process_peak_rss_bytes")
        }
    )
)
print(json.dumps({k: qa[k] for k in ("counts", "events_sha256", "requested_period_status")}))
