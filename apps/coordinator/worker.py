"""Internal worker entry point. Engine results are derived here, never supplied by API."""

import json
from pathlib import Path
import sys
from factory.contracts import (
    ExperimentContract,
    InstrumentSpec,
    StrategySpec,
    fingerprint,
    serialize,
)
from factory.data import Catalog, atomic_bytes
from factory.diagnostics import diagnose_trade
from factory.simulation.runner import replay
from factory.simulation.ledger import require_execution_version
from factory.strategies import compile_signals


def run(payload, root):
    spec = StrategySpec.model_validate(payload["strategy"])
    contract = ExperimentContract.model_validate(payload["contract"])
    profile = InstrumentSpec.model_validate(payload["profile"])
    if contract.strategy_hash != spec.strategy_hash or contract.instrument_hash != fingerprint(
        profile
    ):
        raise ValueError("contract mismatch")
    context = require_execution_version(contract)
    if len(contract.windows) != 1 or any(w.role != "train_only" for w in contract.windows):
        raise ValueError("evaluation worker currently training-only; cannot fabricate OOS")
    catalog = Catalog(Path(root) / "catalog")
    manifest = catalog.verify(contract.dataset_hash)
    if spec.instrument != profile.instrument or manifest["instrument"] != spec.instrument:
        raise ValueError("instrument identity mismatch")
    if not profile.synthetic or not manifest["provenance"].get("synthetic"):
        raise ValueError("HISTORICAL_APPROVAL_REQUIRED: provider and instrument gate not complete")
    quotes = list(catalog.read(contract.dataset_hash))
    window = contract.windows[0]
    quotes = [q for q in quotes if window.start_ns <= q.event_ts_utc_ns < window.end_ns]
    signals = compile_signals(quotes, spec)
    result = replay(
        quotes, profile, spec, signals, contract.scenario == "historical-pessimistic/v1"
    )
    result["runtime_provenance"] = context
    if result["integrity_errors"]:
        raise ValueError("EXECUTION_CONTRACT_MISMATCH: " + serialize(result["integrity_errors"]))
    result["diagnostics"] = [diagnose_trade(t, profile.tick_size) for t in result["trades"]]
    result["signals_screened"] = len(signals)
    if require_execution_version(contract) != context:
        raise ValueError("execution source changed during run")
    digest = fingerprint(result)
    artifact = Path(root) / "artifacts" / f"{contract.experiment_hash}.json"
    if artifact.exists() and artifact.read_text() != serialize(result):
        raise ValueError("immutable artifact differs")
    atomic_bytes(artifact, serialize(result).encode())
    return {"result": result, "artifact_hash": digest}


if __name__ == "__main__":
    try:
        value = run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
        atomic_bytes(sys.argv[3], serialize(value).encode())
    except Exception as exc:
        atomic_bytes(
            sys.argv[3], serialize({"error": type(exc).__name__ + ": " + str(exc)}).encode()
        )
        raise
