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
    compose = subs.add_parser("catalog-compose")
    compose.add_argument("partitions", nargs="+")
    gates = subs.add_parser("readiness")
    gates.add_argument("--evidence", type=Path)
    research = subs.add_parser("research-register")
    research.add_argument("protocol_file", type=Path)
    subs.add_parser("research-status")
    disable = subs.add_parser("research-disable")
    disable.add_argument("protocol_hash")
    subs.add_parser("pause")
    subs.add_parser("resume")
    args = parser.parse_args()
    root = Path(args.state).resolve()
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
