"""Local development commands; production install gates remain explicit."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
from factory.data import atomic_bytes
from factory.experiments import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=os.environ.get("FACTORY_STATE", ".local"))
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init")
    admin = subs.add_parser("create-admin")
    admin.add_argument("--role", choices=["operator", "viewer"], default="operator")
    subs.add_parser("coordinator")
    api = subs.add_parser("serve")
    api.add_argument("--port", type=int, default=8088)
    subs.add_parser("doctor")
    discovery = subs.add_parser("discovery-register")
    discovery.add_argument("policy_file", type=Path)
    subs.add_parser("discovery-status")
    discovery_stop = subs.add_parser("discovery-disable")
    discovery_stop.add_argument("policy_id")
    historical = subs.add_parser("historical-shadow")
    historical.add_argument("request_file", type=Path)
    cohort = subs.add_parser("screen-cohort-freeze")
    cohort.add_argument("request_file", type=Path)
    cohort_report = subs.add_parser("screen-cohort-report")
    cohort_report.add_argument("cohort_id")
    historical_cohort = subs.add_parser("historical-screen-cohort-freeze")
    historical_cohort.add_argument("request_file", type=Path)
    comparability = subs.add_parser("screen-comparability")
    comparability.add_argument("request_file", type=Path)
    quality = subs.add_parser("source-quality")
    quality.add_argument("dataset_hash")
    quality.add_argument("policy_file", type=Path)
    quality.add_argument("--catalog", type=Path)
    quality.add_argument("--calendar-spec", type=Path)
    quality.add_argument("--tzif", type=Path)
    quality.add_argument("--profile", type=Path)
    subs.add_parser("source-quality-status")
    observe = subs.add_parser("source-observe")
    observe.add_argument("slot_file", type=Path)
    observe.add_argument("dataset_hash")
    observe.add_argument("--catalog", type=Path)
    select_source = subs.add_parser("source-select")
    select_source.add_argument("observation_id")
    select_source.add_argument("--catalog", type=Path)
    select_source.add_argument("--actor", required=True)
    select_source.add_argument("--reason", required=True)
    select_source.add_argument("--expected-selection")
    quarantine = subs.add_parser("source-quarantine")
    quarantine.add_argument("observation_id")
    quarantine.add_argument("--actor", required=True)
    quarantine.add_argument("--reason", required=True)
    restore_source = subs.add_parser("source-resolve")
    restore_source.add_argument("quarantine_id")
    restore_source.add_argument("--catalog", type=Path)
    restore_source.add_argument("--actor", required=True)
    restore_source.add_argument("--reason", required=True)
    snapshot = subs.add_parser("source-snapshot")
    snapshot.add_argument("slots_file", type=Path)
    snapshot.add_argument("--catalog", type=Path)
    comparison = subs.add_parser("source-compare")
    comparison.add_argument("left_observation")
    comparison.add_argument("right_observation")
    comparison.add_argument("--catalog", type=Path)
    comparison.add_argument("--max-events-bytes", type=int, default=64 * 1024**2)
    review = subs.add_parser("reference-register")
    review.add_argument("review_file", type=Path)
    review.add_argument("documents", nargs="+", type=Path)
    review.add_argument("--tzif", type=Path)
    admission = subs.add_parser("source-admit")
    admission.add_argument("admission_file", type=Path)
    admission.add_argument("--catalog", type=Path)
    revoke = subs.add_parser("input-revoke")
    revoke.add_argument("review_id")
    revoke.add_argument("--actor", required=True)
    revoke.add_argument("--reason", required=True)
    reviews = subs.add_parser("input-reviews")
    reviews.add_argument("--limit", type=int, default=50)
    reviews.add_argument("--offset", type=int, default=0)
    compose = subs.add_parser("catalog-compose")
    compose.add_argument("partitions", nargs="+")
    gates = subs.add_parser("readiness")
    gates.add_argument("--evidence", type=Path)
    research = subs.add_parser("research-register")
    research.add_argument("protocol_file", type=Path)
    subs.add_parser("research-status")
    disable = subs.add_parser("research-disable")
    disable.add_argument("protocol_hash")
    improve = subs.add_parser("improvement-register")
    improve.add_argument("policy_file", type=Path)
    disable_improvement = subs.add_parser("improvement-disable")
    disable_improvement.add_argument("policy_hash")
    subs.add_parser("improvement-status")
    validation = subs.add_parser("validation-register")
    validation.add_argument("protocol_file", type=Path)
    subs.add_parser("validation-status")
    holdout = subs.add_parser("holdout-reserve")
    holdout.add_argument("spec_file", type=Path)
    freeze = subs.add_parser("holdout-freeze")
    freeze.add_argument("holdout_id")
    freeze.add_argument("training_run_id")
    consume = subs.add_parser("holdout-evaluate")
    consume.add_argument("holdout_id")
    subs.add_parser("holdout-status")
    subs.add_parser("pause")
    subs.add_parser("resume")
    args = parser.parse_args()
    root = Path(args.state).resolve()
    if args.command in (
        "source-observe",
        "source-select",
        "source-quarantine",
        "source-resolve",
        "source-snapshot",
        "source-compare",
    ):
        from factory.data import Catalog
        from factory.data.versions import SourceVersions, SourceSlot

        versions = SourceVersions(root, Catalog(getattr(args, "catalog", None) or root / "catalog"))
        if args.command == "source-observe":
            value = versions.observe(
                SourceSlot.model_validate_json(args.slot_file.read_text()), args.dataset_hash
            )
        elif args.command == "source-select":
            value = versions.select(
                args.observation_id,
                actor=args.actor,
                reason=args.reason,
                expected_selection_id=args.expected_selection,
            )
        elif args.command == "source-quarantine":
            value = {
                "quarantine_id": versions.quarantine(args.observation_id, args.actor, args.reason),
                "observation_id": args.observation_id,
            }
        elif args.command == "source-resolve":
            value = versions.resolve(args.quarantine_id, args.actor, args.reason)
        elif args.command == "source-compare":
            from factory.data.reconcile import compare_sources

            value = compare_sources(
                versions,
                args.left_observation,
                args.right_observation,
                max_events_bytes=args.max_events_bytes,
            )
        else:
            slots = json.loads(args.slots_file.read_text())
            if not isinstance(slots, list):
                parser.error("source snapshot requires an ordered JSON array of slot definitions")
            value = versions.snapshot(slots)
        print(json.dumps(value, indent=2))
        return
    if args.command in ("reference-register", "source-admit", "input-revoke", "input-reviews"):
        from factory.data import Catalog
        from factory.data.admission import InputRegistry, ReferenceReview, AdmissionSpec

        registry = InputRegistry(root, Catalog(getattr(args, "catalog", None) or root / "catalog"))
        if args.command == "reference-register":
            if len(args.documents) > 16:
                parser.error("maximum 16 captured reference documents")
            documents = {}
            for path in args.documents:
                with path.open("rb") as stream:
                    data = stream.read(4 * 1024**2 + 1)
                if len(data) > 4 * 1024**2:
                    parser.error("reference exceeds 4 MiB")
                documents[hashlib.sha256(data).hexdigest()] = data
            value = registry.register_reference(
                ReferenceReview.model_validate_json(args.review_file.read_text()),
                documents,
                tzif=args.tzif.read_bytes() if args.tzif else None,
            )
        elif args.command == "source-admit":
            value = registry.register_admission(
                AdmissionSpec.model_validate_json(args.admission_file.read_text())
            )
        elif args.command == "input-revoke":
            registry.revoke(args.review_id, args.actor, args.reason)
            value = {"revoked": args.review_id}
        else:
            if not 1 <= args.limit <= 200 or args.offset < 0:
                parser.error("input review page requires limit 1..200 and nonnegative offset")
            value = registry.store.rows(
                """SELECT r.*,v.reason revocation_reason
                FROM reviewed_inputs r LEFT JOIN input_revocations v USING(review_id)
                ORDER BY r.created_at,r.review_id LIMIT ? OFFSET ?""",
                (args.limit, args.offset),
            )
        print(json.dumps(value, indent=2))
        return
    if args.command == "source-quality":
        from factory.data import Catalog
        from factory.data.source_quality import SourceQuality, SourceQualityPolicy
        from factory.instruments.calendar import CalendarSpec, SessionCalendar
        from factory.contracts import InstrumentSpec

        if bool(args.calendar_spec) != bool(args.tzif):
            parser.error("calendar specification and captured TZif bytes must be supplied together")
        calendar = (
            SessionCalendar(
                CalendarSpec.model_validate_json(args.calendar_spec.read_text()),
                args.tzif.read_bytes(),
            )
            if args.calendar_spec
            else None
        )
        profile = (
            InstrumentSpec.model_validate_json(args.profile.read_text()) if args.profile else None
        )
        result = SourceQuality(root, Catalog(args.catalog or root / "catalog")).run(
            args.dataset_hash,
            SourceQualityPolicy.model_validate_json(args.policy_file.read_text()),
            calendar=calendar,
            profile=profile,
        )
        print(json.dumps(result, indent=2))
        if (
            result["source_structural_status"] != "PASS"
            or result["profile_status"] == "DECLARED_UNITS_MISMATCH"
            or result["calendar_status"] == "UNRESOLVED_CALENDAR"
            or result["requested_period_status"] == "OBSERVED_OUTSIDE_REQUESTED_PERIOD"
        ):
            raise SystemExit(1)
        return
    if args.command == "source-quality-status":
        print(
            json.dumps(
                Store(root / "factory.sqlite").rows(
                    "SELECT run_id,report_sha256,events_sha256,created_at FROM source_quality_receipts ORDER BY created_at DESC"
                ),
                indent=2,
            )
        )
        return
    if args.command == "catalog-compose":
        from factory.data import Catalog

        print(json.dumps(Catalog(root / "catalog").compose(args.partitions), indent=2))
        return
    if args.command == "readiness":
        from factory.operations.readiness import readiness

        evidence = json.loads(args.evidence.read_text()) if args.evidence else {}
        report = readiness(root, evidence)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["OPERATION_READY"] else 1)
    if args.command == "doctor":
        import platform
        import psutil
        import shutil

        print(
            json.dumps(
                {
                    "os": platform.platform(),
                    "python": platform.python_version(),
                    "logical_cpu": os.cpu_count(),
                    "ram_bytes": psutil.virtual_memory().total,
                    "disk_free_bytes": shutil.disk_usage(".").free,
                    "operation_ready": False,
                    "reason": "Development checkpoint; release gates pending",
                },
                indent=2,
            )
        )
        raise SystemExit(1)
    Store(root / "factory.sqlite")
    if args.command in ("discovery-register", "discovery-status", "discovery-disable"):
        from factory.exploration.discovery import Discovery, DiscoveryPolicy

        manager = Discovery(Store(root / "factory.sqlite"), root)
        if args.command == "discovery-register":
            if args.policy_file.stat().st_size > 65536:
                raise ValueError("discovery policy exceeds input budget")
            identity = manager.register(
                DiscoveryPolicy.model_validate_json(args.policy_file.read_text())
            )
            print(json.dumps({"policy_id": identity, "research_paused": manager.store.paused()}))
        elif args.command == "discovery-disable":
            manager.disable(args.policy_id)
            print(json.dumps({"policy_id": args.policy_id, "enabled": False}))
        else:
            print(json.dumps(manager.status()))
    elif args.command in ("screen-cohort-freeze", "screen-cohort-report"):
        from factory.screening.cohorts import Cohorts, CohortRequest

        cohorts = Cohorts(Store(root / "factory.sqlite"), root)
        if args.command == "screen-cohort-freeze":
            if args.request_file.stat().st_size > 65536:
                raise ValueError("cohort request exceeds input budget")
            identity = cohorts.freeze(
                CohortRequest.model_validate_json(args.request_file.read_text())
            )
            print(json.dumps({"cohort_id": identity, "paused": cohorts.store.paused()}))
        else:
            print(json.dumps(cohorts.report(args.cohort_id)))
    elif args.command == "screen-comparability":
        from factory.screening.comparability import Comparability, ComparabilityRequest

        service = Comparability(Store(root / "factory.sqlite"), root)
        if args.request_file.stat().st_size > 65536:
            raise ValueError("comparability request exceeds input budget")
        print(
            json.dumps(
                service.compare(
                    ComparabilityRequest.model_validate_json(args.request_file.read_text())
                ),
                indent=2,
            )
        )
    elif args.command == "historical-screen-cohort-freeze":
        from factory.screening.historical_cohorts import (
            HistoricalCohortRequest,
            HistoricalCohorts,
        )

        cohorts = HistoricalCohorts(Store(root / "factory.sqlite"), root)
        if args.request_file.stat().st_size > 65536:
            raise ValueError("historical cohort request exceeds input budget")
        identity = cohorts.freeze(
            HistoricalCohortRequest.model_validate_json(args.request_file.read_text())
        )
        print(json.dumps({"cohort_id": identity, "paused": cohorts.store.paused()}))
    elif args.command == "historical-shadow":
        from factory.screening.historical import HistoricalShadowRequest, diagnose

        if args.request_file.stat().st_size > 65536:
            raise ValueError("historical shadow request exceeds input budget")
        print(
            json.dumps(
                diagnose(
                    root, HistoricalShadowRequest.model_validate_json(args.request_file.read_text())
                )
            )
        )
    elif args.command == "create-admin":
        path = root / "access.json"
        key = secrets.token_urlsafe(32)
        keys = json.loads(path.read_text()) if path.exists() else []
        keys.append({"role": args.role, "sha256": hashlib.sha256(key.encode()).hexdigest()})
        old = os.umask(0o077)
        try:
            atomic_bytes(path, json.dumps(keys).encode())
        finally:
            os.umask(old)
        token_file = root / f"{args.role}-{len(keys)}.token"
        fd = os.open(token_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key)
        print(f"Credential written with mode 0600 to {token_file}; do not commit or log it.")
    elif args.command == "validation-register":
        from factory.validation.protocol import ValidationController, ValidationProtocol

        identity = ValidationController(Store(root / "factory.sqlite"), root).register(
            ValidationProtocol.model_validate_json(args.protocol_file.read_text())
        )
        print(
            json.dumps(
                {"protocol_id": identity, "scope": "controlled synthetic chronological validation"}
            )
        )
    elif args.command == "validation-status":
        store = Store(root / "factory.sqlite")
        print(
            json.dumps(
                store.rows(
                    "SELECT p.protocol_id,c.enabled,json_extract(r.report_json,'$.status') status FROM validation_protocols p JOIN validation_controls c USING(protocol_id) LEFT JOIN validation_protocol_reports r USING(protocol_id) ORDER BY p.created_at,p.protocol_id"
                ),
                indent=2,
            )
        )
    elif args.command.startswith("holdout-"):
        from factory.validation.access import HoldoutSpec, Holdouts

        holdouts = Holdouts(root)
        if args.command == "holdout-reserve":
            value = {
                "holdout_id": holdouts.register(
                    HoldoutSpec.model_validate_json(args.spec_file.read_text())
                )
            }
        elif args.command == "holdout-freeze":
            value = holdouts.freeze(args.holdout_id, args.training_run_id)
        elif args.command == "holdout-evaluate":
            value = holdouts.enqueue(args.holdout_id)
        else:
            value = holdouts.status()
        print(json.dumps(value, indent=2))
    elif args.command.startswith("improvement-"):
        from factory.improvement.service import Improvement, ImprovementPolicy

        improvement = Improvement(Store(root / "factory.sqlite"), root)
        if args.command == "improvement-register":
            identity = improvement.register(
                ImprovementPolicy.model_validate_json(args.policy_file.read_text())
            )
            print(
                json.dumps({"policy_hash": identity, "scope": "bounded training improvement only"})
            )
        elif args.command == "improvement-disable":
            improvement.disable(args.policy_hash)
            print(json.dumps({"policy_hash": args.policy_hash, "enabled": False}))
        else:
            print(json.dumps(improvement.status(), indent=2))
    elif args.command.startswith("research-"):
        from factory.exploration.persistent import Search, SearchProtocol, status

        store = Store(root / "factory.sqlite")
        search = Search(store, root)
        if args.command == "research-register":
            identity = search.register(
                SearchProtocol.model_validate_json(args.protocol_file.read_text())
            )
            print(
                json.dumps(
                    {
                        "protocol_hash": identity,
                        "paused": store.paused(),
                        "scope": "synthetic training only",
                    }
                )
            )
        elif args.command == "research-disable":
            search.set_enabled(args.protocol_hash, False, actor="local-owner")
            print(json.dumps({"protocol_hash": args.protocol_hash, "enabled": False}))
        else:
            print(json.dumps(status(store), indent=2))
    elif args.command in ("pause", "resume"):
        store = Store(root / "factory.sqlite")
        store.pause(args.command == "pause", "local-owner")
        print(json.dumps({"paused": store.paused()}))
    elif args.command == "serve":
        import uvicorn
        from apps.api.main import create_app

        uvicorn.run(create_app(root, "apps/dashboard/build"), host="127.0.0.1", port=args.port)
    elif args.command == "coordinator":
        from apps.coordinator.service import serve

        serve(root)
    else:
        print("State initialized; research paused by default.")


if __name__ == "__main__":
    main()
