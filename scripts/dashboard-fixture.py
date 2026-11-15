"""Create fresh, explicitly synthetic, paused state for the real browser rehearsal."""

import argparse
from pathlib import Path
import subprocess
import sys

from factory.contracts import serialize
from factory.data import atomic_bytes
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol
from factory.operations.fixtures import seed
from factory.provenance import source_identity

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
if args.state.exists():
    parser.error("state must be new; preserve previous QA evidence")
payload = seed(args.state, 240)
store = Store(args.state / "factory.sqlite")
p = SearchProtocol(
    dataset_hash=payload["contract"]["dataset_hash"],
    profile=payload["profile"],
    window=payload["contract"]["windows"][0],
    family="momentum",
    timeframe="M1",
    code_revision=payload["contract"]["code_revision"],
    seed=42,
    max_trials=2,
)
identity = Search(store, args.state).register(p)
job = store.enqueue("research", payload, payload["contract"]["strategy_hash"], actor="browser-qa")
atomic_bytes(
    args.state / "qa.json",
    serialize({"protocol_hash": identity, "job_id": job, "source": source_identity()}).encode(),
)
subprocess.run(
    [sys.executable, "-m", "factory.cli", "--state", str(args.state), "create-admin"], check=True
)
print("Paused synthetic QA state created; no coordinator started")
