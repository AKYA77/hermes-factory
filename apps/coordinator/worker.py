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
from factory.strategies import compile_signals


def run(payload, root):
    spec = StrategySpec.model_validate(payload["strategy"])
    contract = ExperimentContract.model_validate(payload["contract"])
    profile = InstrumentSpec.model_validate(payload["profile"])
    if contract.strategy_hash != spec.strategy_hash or contract.instrument_hash != fingerprint(
        profile
    ):
        raise ValueError("contract mismatch")
    if contract.engine_version != "1.231.0" or contract.fill_version != "adverse-fill/v1":
        raise ValueError("unsupported engine/fill version")
    if any(w.role != "train_only" for w in contract.windows):
        raise ValueError("evaluation worker currently training-only; cannot fabricate OOS")
    quotes = list(Catalog(Path(root) / "catalog").read(contract.dataset_hash))
    window = contract.windows[0]
    quotes = [q for q in quotes if window.start_ns <= q.event_ts_utc_ns < window.end_ns]
    signals = compile_signals(quotes, spec)
    result = replay(
        quotes, profile, spec, signals, contract.scenario == "historical-pessimistic/v1"
    )
    result["diagnostics"] = [diagnose_trade(t, profile.tick_size) for t in result["trades"]]
    result["signals_screened"] = len(signals)
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
