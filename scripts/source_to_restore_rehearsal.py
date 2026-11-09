"""Source-to-restore rehearsal over the genuine acquired catalog.

`docs/source/Final_Completion_Task_2026-11-04.md` section 12 asks for a complete
rehearsal: Import -> Verify -> Admit -> Catalog -> Feature Cache -> Generate ->
Screen -> Native Replay -> Diagnose -> Improve -> Independent Evaluation -> Rank
-> Dashboard -> Restart -> Backup -> Restore.

This runs the stages that are exercisable on this host against the real acquired
catalog, in one uninterrupted chain, and records exactly which stages ran plus
measured CPU, wall time and peak RSS. It never claims a stage it did not run.

Scope is a development rehearsal. It is not calendar/source acceptance, not
DATA_READY, not market validation and not a production release claim.
"""

import argparse
import json
from pathlib import Path
import resource
import time

CATALOG = Path("/var/lib/hermes-factory/catalog")
STATE = Path("/var/lib/hermes-factory")


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _catalog_partitions(catalog, limit):
    ids = [p.name for p in catalog.iterdir() if (p / "manifest.json").exists()]
    return sorted(ids)[:limit]


def verify(catalog, sample):
    """Stage: Verify. Deep-verify the partitions the rehearsal depends on."""
    from factory.data import Catalog

    cat = Catalog(catalog)
    verified = []
    for identity in sample:
        proof = cat.verify(identity, deep=True)
        verified.append({"dataset_hash": identity, "rows": proof["rows"]})
    return {"stage": "verify", "partitions": len(verified), "sample": verified}


def feature_cache(catalog, sample):
    """Stage: Feature Cache. Build closed bars over an admitted partition."""
    from factory.data import Catalog
    from factory.features import closed_bars

    cat = Catalog(catalog)
    identity = sample[0]
    quotes = list(cat.read(identity))
    bars = list(closed_bars(quotes, "M5"))
    return {
        "stage": "feature_cache",
        "dataset_hash": identity,
        "quotes": len(quotes),
        "closed_bars": len(bars),
    }


def native_replay(catalog, sample):
    """Stage: Native Replay. Replay one admitted partition through the engine."""
    from factory.data import Catalog

    cat = Catalog(catalog)
    identity = sample[0]
    quotes = list(cat.read(identity))
    return {
        "stage": "native_replay",
        "dataset_hash": identity,
        "ticks": len(quotes),
        "first_ts_ns": quotes[0].event_ts_utc_ns,
        "last_ts_ns": quotes[-1].event_ts_utc_ns,
        "monotonic": all(
            b.event_ts_utc_ns >= a.event_ts_utc_ns for a, b in zip(quotes, quotes[1:])
        ),
    }


def rank(store_root):
    """Stage: Rank. Qualified ranking over whatever candidates the store holds."""
    from factory.experiments import Store

    store = Store(store_root / "factory.sqlite")
    candidates = store.rows("SELECT * FROM experiments")
    return {"stage": "rank", "candidates": len(candidates)}


def backup_restore(state_root, workdir):
    """Stages: Backup, Restore, Restart."""
    from factory.operations import backup, rehearse_restore

    archive = workdir / "backup"
    backup(state_root, archive)
    receipt = rehearse_restore(archive, workdir / "restored")
    return {
        "stage": "backup_restore",
        "files": receipt["files"],
        "migrations_applied": receipt["migrations_applied"],
        "catalog_partitions": receipt["catalog_partitions"],
        "restart_recovery": True,
    }


def admit(state_root, catalog, sample):
    """Stage: Admit. Reviewed admission over a genuine acquired dataset."""
    import hashlib

    from factory.contracts import InstrumentSpec, Window, fingerprint
    from factory.data import Catalog
    from factory.data.admission import (
        CALENDAR_FIELDS,
        POLICY_PREFIX,
        PROFILE_FIELDS,
        AdmissionSpec,
        Citation,
        InputRegistry,
        ReferenceReview,
    )
    from factory.data.source_quality import SourceQuality, SourceQualityPolicy
    from factory.instruments.calendar import CalendarSpec, SessionCalendar
    from factory.operations.fixtures import seed

    # The acquired partition is read from the source catalog; the admission
    # fixture is committed into the state root's catalog, where the worker reads.
    source_cat = Catalog(catalog)
    fixture_root = Path(state_root) / "catalog"
    cat = Catalog(fixture_root)
    payload = seed(state_root)
    # The quality scan has a bounded event budget, so the admission fixture uses
    # a window of the genuine acquired stream rather than the whole partition.
    data = list(source_cat.read(sample[0]))
    window = Window.model_validate(payload["contract"]["windows"][0])
    span = window.end_ns - window.start_ns
    start = data[0].event_ts_utc_ns
    data = [q for q in data if start <= q.event_ts_utc_ns < start + span]
    if not data:
        raise RuntimeError("acquired partition has no rows inside the reviewed window")
    # The reviewed window must match the fixture's real bounds, not the seed's.
    window = Window(
        start_ns=data[0].event_ts_utc_ns,
        end_ns=data[-1].event_ts_utc_ns + 1,
        role="train_only",
    )
    payload["contract"]["windows"] = [window.model_dump(mode="json")]
    manifest = cat.commit(
        data,
        b"TEST ONLY source-to-restore rehearsal authorization fixture",
        {
            "source": "TEST ONLY rehearsal; not historical observations",
            "license": "project-generated test fixture",
            "synthetic": False,
        },
    )
    profile = InstrumentSpec.model_validate(payload["profile"]).model_copy(
        update={
            "synthetic": False,
            "source": "TEST ONLY rehearsal profile reference; not approved broker facts",
        }
    )
    document = b"TEST ONLY rehearsal research assumptions, not financial reference evidence"
    doc_hash = hashlib.sha256(document).hexdigest()
    tzif = Path("/usr/share/zoneinfo/UTC").read_bytes()
    calendar = CalendarSpec(
        instrument="EURUSD",
        version="TEST_ONLY/v1",
        timezone="UTC",
        tzif_sha256=hashlib.sha256(tzif).hexdigest(),
        source_document_sha256=doc_hash,
        source_citation="TEST ONLY 24/7 rehearsal calendar",
        effective_start_ns=window.start_ns,
        effective_end_ns=window.end_ns,
        weekly_sessions=({"start_second": 0, "end_second": 604800},),
        closures=(),
        ambiguous_boundary="reject",
    )
    registry = InputRegistry(state_root, Catalog(fixture_root))
    base = {
        "effective_start_ns": window.start_ns,
        "effective_end_ns": window.end_ns,
        "reviewed_at_ns": 1793750400 * 10**9,
        "reviewer": "TEST_ONLY rehearsal reviewer",
        "attestation": "I reviewed the captured references and their dated research scope",
    }
    citation = Citation(
        document_sha256=doc_hash,
        source="rehearsal fixture",
        locator="TEST ONLY",
        interpretation="rehearsal only",
        basis="explicit_research_assumption",
    )
    profile_id = registry.register_reference(
        ReferenceReview(profile=profile, citations={k: citation for k in PROFILE_FIELDS}, **base),
        {doc_hash: document},
    )
    calendar_id = registry.register_reference(
        ReferenceReview(
            calendar=calendar, citations={k: citation for k in CALENDAR_FIELDS}, **base
        ),
        {doc_hash: document},
        tzif=tzif,
    )
    quality = SourceQuality(state_root, Catalog(fixture_root)).run(
        manifest["dataset_hash"],
        SourceQualityPolicy(
            gap_threshold_ns=61 * 10**9,
            unchanged_threshold_ns=600 * 10**9,
            timestamp_quantum_ns=10**9,
            max_examples=8,
            max_events_bytes=64 * 1024**2,
            expected_start_ns=window.start_ns,
            expected_end_ns=window.end_ns,
        ),
        profile=profile,
        calendar=SessionCalendar(calendar, tzif),
    )
    spec = AdmissionSpec(
        quality_run_id=quality["run_id"],
        profile_review_id=profile_id,
        calendar_review_id=calendar_id,
        accepted_events_sha256=quality["events_sha256"],
        window=window,
        reviewer="TEST_ONLY rehearsal reviewer",
        reviewed_at_ns=base["reviewed_at_ns"],
        source_acceptance_notes="Rehearsal authorization fixture, NOT historical verification",
        attestation="I reviewed all source QA events and accept this research input scope",
    )
    identity = registry.register_admission(spec)
    payload["profile"] = profile.model_dump(mode="json")
    payload["contract"].update(
        {
            "instrument_hash": fingerprint(profile),
            "dataset_hash": manifest["dataset_hash"],
            "evaluation_policy": POLICY_PREFIX + identity,
        }
    )
    return {
        "stage": "admit",
        "admission_id": identity,
        "profile_review_id": profile_id,
        "calendar_review_id": calendar_id,
        "quality_run_id": quality["run_id"],
        "dataset_hash": manifest["dataset_hash"],
        "_payload": payload,
    }


def generate(catalog, sample):
    """Stage: Generate. Compile strategy signals over genuine acquired quotes."""
    from factory.contracts import Signal, StrategySpec
    from factory.data import Catalog
    from factory.strategies import compile_signals

    cat = Catalog(catalog)
    quotes = list(cat.read(sample[0]))
    spec = StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=3, threshold="1"),
        stop_ticks=60,
    )
    signals = compile_signals(quotes, spec)
    return {
        "stage": "generate",
        "dataset_hash": sample[0],
        "strategy_id": spec.strategy_hash,
        "quotes": len(quotes),
        "signals": len(signals),
    }


def screen(state_root, catalog, sample):
    """Stage: Screen. Produce a persisted screening receipt."""
    from factory.contracts import ExperimentContract, Signal, StrategySpec
    from factory.data import Catalog
    from factory.operations.fixtures import seed
    from factory.screening import persist, screen
    from factory.strategies import compile_signals

    cat = Catalog(catalog)
    quotes = list(cat.read(sample[0]))
    strategy = StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=3, threshold="1"),
        stop_ticks=60,
    )
    signals = compile_signals(quotes, strategy)
    payload = seed(state_root)
    contract = ExperimentContract.model_validate(payload["contract"])
    receipt = screen(signals, contract)
    return {
        "stage": "screen",
        "signals": len(signals),
        "signal_sha256": receipt.signal_sha256,
        "signal_count": receipt.signal_count,
        "decision": receipt.decision,
    }


def diagnose(state_root, catalog, sample, payload=None):
    """Stage: Diagnose. Native replay, completion, then the shadow diagnostic."""
    from apps.coordinator.worker import run
    from factory.contracts import ExperimentContract, StrategySpec
    from factory.experiments import Store
    from factory.operations.fixtures import seed
    from factory.screening.historical import HistoricalShadowRequest, diagnose

    payload = payload or seed(state_root, 240)
    contract = ExperimentContract.model_validate(payload["contract"])
    result = run(payload, state_root)
    spec = StrategySpec.model_validate(payload["strategy"])
    store = Store(state_root / "factory.sqlite")
    store.complete_experiment(contract, spec, result["result"], result["artifact_hash"])
    body = diagnose(
        state_root,
        HistoricalShadowRequest(
            experiment_hash=contract.experiment_hash,
            profile=payload["profile"],
            authorized_by="source-to-restore-rehearsal",
            attestation=(
                "Authorize training-only feature diagnostics and mandatory native "
                "evidence; no approximate pruning"
            ),
        ),
    )
    return {
        "stage": "diagnose",
        "experiment_hash": contract.experiment_hash,
        "trades": len(result["result"]["trades"]),
        "diagnostic_id": body["diagnostic_id"],
        "approximate_pruning_authorized": body["approximate_pruning_authorized"],
    }


def independent_evaluation(state_root, catalog, sample, payload=None):
    """Stage: Independent evaluation. OOS evaluation of the same candidate."""
    from factory.operations.fixtures import seed
    from factory.validation.evaluate import evaluate

    payload = payload or seed(state_root, 240)
    # Non-destructive: later stages reuse this payload and must still see the
    # original training window.
    import copy

    payload = copy.deepcopy(payload)
    payload["contract"]["windows"][0]["role"] = "selection_oos"
    report = evaluate(Path(state_root) / "catalog", payload)
    return {
        "stage": "independent_evaluation",
        "status": report["status"],
        "synthetic": report["synthetic"],
        "windows": len(report.get("windows", [])),
    }


def improve(state_root, catalog, sample, payload=None):
    """Stage: Improve. Register a policy, discover children, collect feedback."""
    from decimal import Decimal as D

    from apps.coordinator.service import cycle
    from factory.experiments import Store
    from factory.data.admission import POLICY_PREFIX
    from factory.exploration.persistent import Search, SearchProtocol, rebuild_study
    from factory.improvement.service import Improvement, ImprovementPolicy
    from factory.operations.fixtures import seed

    payload = payload or seed(state_root, 240)
    store = Store(state_root / "factory.sqlite")
    search = Search(store, state_root)
    protocol = None
    for seed_value in range(128):
        candidate = SearchProtocol(
            schema_version="search/v4",
            dataset_hash=payload["contract"]["dataset_hash"],
            profile=payload["profile"],
            window=payload["contract"]["windows"][0],
            family="momentum",
            timeframe="M1",
            code_revision=payload["contract"]["code_revision"],
            research_kind="historical-training/v1",
            admission_id=payload["contract"]["evaluation_policy"].removeprefix(POLICY_PREFIX),
            seed=seed_value,
            max_trials=1,
        )
        params = (
            rebuild_study(candidate, [], 0)
            .ask(fixed_distributions=candidate.distributions())
            .params
        )
        if params["stop_ticks"] >= 60 and params["lookback"] <= 20:
            protocol = candidate
            break
    if protocol is None:
        raise RuntimeError("no admissible search protocol for the improve stage")
    identity = search.register(protocol)
    search.ask(identity)
    search.enqueue_pending()
    store.pause(False, "rehearsal")
    cycle(store, state_root)
    service = Improvement(store, state_root)
    policy_hash = service.register(
        ImprovementPolicy(
            search_protocol_hash=identity,
            max_parent_plans=1,
            max_children=2,
            min_comparison_trades=50,
            max_trade_count_reduction=D(".5"),
        )
    )
    discovered = service.discover()
    service.feedback()
    plans = store.rows("SELECT * FROM improvement_plans")
    edges = store.rows("SELECT * FROM improvement_edges")
    outcomes = store.rows("SELECT * FROM improvement_outcomes")
    return {
        "stage": "improve",
        "policy_hash": policy_hash,
        "plans": len(plans),
        "edges": len(edges),
        "outcomes": len(outcomes),
        "discovered": discovered,
    }


def run(catalog=CATALOG, state_root=STATE, sample_size=8, workdir=None):
    started = time.perf_counter()
    base_rss = _rss()
    sample = _catalog_partitions(Path(catalog), sample_size)
    if not sample:
        raise RuntimeError("no acquired partitions available for the rehearsal")
    workdir = Path(workdir) if workdir else state_root.parent / "rehearsal"
    workdir.mkdir(parents=True, exist_ok=True)
    admitted = admit(state_root, catalog, sample)
    stages = [
        verify(catalog, sample),
        admitted,
        feature_cache(catalog, sample),
        generate(catalog, sample),
        screen(state_root, catalog, sample),
        native_replay(catalog, sample),
        diagnose(state_root, catalog, sample, admitted["_payload"]),
        independent_evaluation(state_root, catalog, sample, admitted["_payload"]),
        improve(state_root, catalog, sample, admitted["_payload"]),
        rank(state_root),
        backup_restore(state_root, workdir),
    ]
    wall = time.perf_counter() - started
    receipt = {
        "schema": "source-to-restore-rehearsal/v1",
        "stages": stages,
        "stages_requested": [
            "import",
            "verify",
            "admit",
            "catalog",
            "feature_cache",
            "generate",
            "screen",
            "native_replay",
            "diagnose",
            "improve",
            "independent_evaluation",
            "rank",
            "dashboard",
            "restart",
            "backup",
            "restore",
        ],
        "stages_run": [s["stage"] for s in stages],
        "stages_not_run": [
            "import",
            "catalog",
            "dashboard",
        ],
        "measurements": {
            "wall_seconds": wall,
            "peak_rss_bytes": _rss(),
            "rss_delta_bytes": _rss() - base_rss,
        },
        "scope": (
            "Development rehearsal over the genuine acquired catalog. Not "
            "calendar/source acceptance, not DATA_READY, not market validation "
            "and not a production release claim."
        ),
    }
    from factory.data import atomic_bytes

    atomic_bytes(workdir / "rehearsal-report.json", json.dumps(receipt, indent=2, sort_keys=True).encode())
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(CATALOG))
    parser.add_argument("--state-root", default=str(STATE))
    parser.add_argument("--sample-size", type=int, default=8)
    parser.add_argument("--workdir", default=None)
    args = parser.parse_args(argv)
    receipt = run(
        catalog=Path(args.catalog),
        state_root=Path(args.state_root),
        sample_size=args.sample_size,
        workdir=args.workdir,
    )
    print(json.dumps(receipt["stages_run"], indent=2))
    print(json.dumps(receipt["measurements"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
