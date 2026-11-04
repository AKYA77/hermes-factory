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
    quality = subs.add_parser("source-quality")
    quality.add_argument("dataset_hash")
    quality.add_argument("policy_file", type=Path)
    quality.add_argument("--catalog", type=Path)
    quality.add_argument("--calendar-spec", type=Path)
    quality.add_argument("--tzif", type=Path)
    quality.add_argument("--profile", type=Path)
    subs.add_parser("source-quality-status")
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
    if args.command == "create-admin":
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
