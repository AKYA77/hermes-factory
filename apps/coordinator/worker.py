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
from factory.strategies import iter_bar_signals
from factory.features.disk import BarCache
from factory.screening import SCREEN_POLICY, screen, persist


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
    manifest = catalog.verify(contract.dataset_hash, deep=True)
    if spec.instrument != profile.instrument or manifest["instrument"] != spec.instrument:
        raise ValueError("instrument identity mismatch")
    if not profile.synthetic or not manifest["provenance"].get("synthetic"):
        raise ValueError("HISTORICAL_APPROVAL_REQUIRED: provider and instrument gate not complete")
    window = contract.windows[0]
    from factory.experiments import Store
    from factory.validation.access import training_use

    with Store(Path(root) / "factory.sqlite").transaction() as db:
        training_use(db, profile, contract, contract.experiment_hash, "training-execution")

    def read_window():
        return catalog.read(contract.dataset_hash, start_ns=window.start_ns, end_ns=window.end_ns)

    generated = 0

    def signals():
        nonlocal generated
        for signal in iter_bar_signals(events, spec):
            generated += 1
            yield signal

    cache = BarCache(Path(root) / "cache" / "bars")
    screening = payload.get("screening")
    receipt = None
    if screening is not None:
        if screening != SCREEN_POLICY:
            raise ValueError("unsupported screening policy")
        with cache.events(
            catalog,
            contract.dataset_hash,
            contract.instrument_hash,
            contract.code_revision,
            (spec.timeframe, *spec.confirmations),
            start_ns=window.start_ns,
            end_ns=window.end_ns,
        ) as events:
            receipt = screen(iter_bar_signals(events, spec), contract)
        catalog.verify(contract.dataset_hash, deep=True)
        if require_execution_version(contract) != context:
            raise ValueError("execution source changed during screen")
        screen_hash = persist(root, receipt)
        if receipt.decision == "PRUNE_NO_SIGNALS":
            return {
                "result_kind": "SCREENED_OUT",
                "screen": receipt.model_dump(mode="json"),
                "screen_artifact_hash": screen_hash,
            }
    with cache.events(
        catalog,
        contract.dataset_hash,
        contract.instrument_hash,
        contract.code_revision,
        (spec.timeframe, *spec.confirmations),
        start_ns=window.start_ns,
        end_ns=window.end_ns,
    ) as events:
        result = replay(
            read_window(),
            profile,
            spec,
            signals(),
            contract.scenario == "historical-pessimistic/v1",
            inline_paths=False,
            dataset_hash=contract.dataset_hash,
            spool_directory=Path(root),
        )
    catalog.verify(contract.dataset_hash, deep=True)
    result["runtime_provenance"] = context
    if receipt is not None:
        result["tier0_screen"] = receipt.model_dump(mode="json")
        if receipt.decision == "AUDIT_NO_SIGNALS":
            audit_passed = not (
                result["fills"] or result["trades"] or result["open_trade"] or generated
            )
            result["tier0_audit"] = {"passed": audit_passed, "false_negative": not audit_passed}
            if not audit_passed:
                result["integrity_errors"].append({"reason": "TIER0_FALSE_NEGATIVE"})
    if result["integrity_errors"]:
        quarantine = {
            "status": "QUARANTINED_EXECUTION_CONTRACT_MISMATCH",
            "experiment_hash": contract.experiment_hash,
            "contract": contract.model_dump(mode="json"),
            "strategy": spec.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "result": result,
        }
        quarantine_hash = fingerprint(quarantine)
        failed = (
            Path(root)
            / "artifacts"
            / "failed"
            / f"{contract.experiment_hash}-{quarantine_hash}.json"
        )
        atomic_bytes(failed, serialize(quarantine).encode())
        raise ValueError(
            "EXECUTION_CONTRACT_MISMATCH: "
            + serialize(result["integrity_errors"])
            + "; quarantined_artifact_sha256="
            + quarantine_hash
        )
    result["diagnostics"] = [diagnose_trade(t, profile.tick_size) for t in result["trades"]]
    result["signals_screened"] = generated
    result["open_trade_diagnostics"] = (
        diagnose_trade(result["open_trade"], profile.tick_size) if result["open_trade"] else None
    )
    if require_execution_version(contract) != context:
        raise ValueError("execution source changed during run")
    digest = fingerprint(result)
    artifact = Path(root) / "artifacts" / f"{contract.experiment_hash}.json"
    if artifact.exists() and artifact.read_text() != serialize(result):
        raise ValueError("immutable artifact differs")
    atomic_bytes(artifact, serialize(result).encode())
    return {"result": result, "artifact_hash": digest}


if __name__ == "__main__":
    import os
    import resource

    # Linux target: an abruptly killed coordinator must not leave an orphan
    # engine consuming resources after its fenced lease has been reclaimed.
    parent = os.environ.get("FACTORY_SUPERVISED_PARENT_PID")
    if parent:
        from apps.coordinator.supervision import bind_parent

        bind_parent(int(parent))

    def measured(value):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {**value, "resources": {"peak_rss_bytes": usage.ru_maxrss * 1024}}

    try:
        value = run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
        atomic_bytes(sys.argv[3], serialize(measured(value)).encode())
    except Exception as exc:
        atomic_bytes(
            sys.argv[3],
            serialize(measured({"error": type(exc).__name__ + ": " + str(exc)})).encode(),
        )
        raise
