"""Fresh multi-quarter synthetic state for real validation browser controls."""

import argparse
from dataclasses import replace, asdict
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from factory.contracts import serialize, Window
from factory.data import Catalog, atomic_bytes
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol
from factory.operations.fixtures import seed
from factory.provenance import source_identity

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
if args.state.exists():
    parser.error("new isolated state required")
payload = seed(args.state, 480)
catalog = Catalog(args.state / "catalog")
original = list(catalog.read(payload["contract"]["dataset_hash"]))
partitions = []
for month in (1, 4, 7, 10):
    timestamp = int(datetime(2025, month, 1, tzinfo=timezone.utc).timestamp()) * 10**9
    data = [
        replace(
            q,
            event_ts_utc_ns=timestamp + i * 60 * 10**9,
            ingest_batch_id=f"validation-browser-quarter-{month}",
        )
        for i, q in enumerate(original)
    ]
    manifest = catalog.commit(
        data,
        serialize([asdict(q) for q in data]).encode(),
        {
            "source": "synthetic multi-quarter browser acceptance fixture",
            "synthetic": True,
            "license": "project-generated software test fixture",
        },
    )
    partitions.append(manifest["dataset_hash"])
view = catalog.compose(partitions)
# Register training influence only in January. October remains prospectively
# reservable; a full-span training registration would correctly block it.
window = Window.model_validate(payload["contract"]["windows"][0])
protocol = SearchProtocol(
    dataset_hash=view["dataset_hash"],
    profile=payload["profile"],
    window=window,
    family="momentum",
    timeframe="M1",
    code_revision=payload["contract"]["code_revision"],
    seed=42,
    max_trials=2,
)
store = Store(args.state / "factory.sqlite")
identity = Search(store, args.state).register(protocol)
atomic_bytes(
    args.state / "qa.json",
    serialize(
        {
            "protocol_hash": identity,
            "source": source_identity(),
            "dataset_hash": view["dataset_hash"],
            "scope": "synthetic paused UI fixture; no historical metrics",
        }
    ).encode(),
)
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(args.state), "create-admin"], check=True
)
print("Paused synthetic multi-quarter UI state created; coordinator not started")
