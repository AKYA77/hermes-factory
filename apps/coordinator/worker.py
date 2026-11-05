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
from factory.features.indicators import compiler_events
from factory.screening import SCREEN_POLICY, screen, from_summary, persist
from factory.screening.labels import CostHorizonPolicy, estimate_labels


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
    admission = None
    registry = None
    if bool(manifest["provenance"].get("synthetic")) != profile.synthetic:
        raise ValueError("source/profile evidence kind mismatch")
    if not profile.synthetic:
        from factory.data.admission import InputRegistry

        registry = InputRegistry(root, catalog)
        admission = registry.require(contract, profile)
        if payload.get("screening") is not None:
            raise ValueError("historical Tier 0 requires its own approved screening policy")
    window = contract.windows[0]
    from factory.experiments import Store
    from factory.validation.access import training_use
    from factory.data.versions import reject_quarantined

    with Store(Path(root) / "factory.sqlite").transaction() as db:
        reject_quarantined(db, manifest)
        training_use(db, profile, contract, contract.experiment_hash, "training-execution")

    def read_window():
        return catalog.read(contract.dataset_hash, start_ns=window.start_ns, end_ns=window.end_ns)

    generated = 0

    def signals():
        nonlocal generated
        for signal in iter_bar_signals(events, spec, transform_lookup=transform_lookup):
            generated += 1
            yield signal

    cache = BarCache(Path(root) / "cache" / "bars")
    screening = payload.get("screening")
    from factory.screening.fallback import status as screening_status

    pruning_enabled = screening_status(Store(Path(root) / "factory.sqlite"))["enabled"]
    from factory.screening.cohorts import selected_cohort

    audit_cohort = selected_cohort(Store(Path(root) / "factory.sqlite"), contract)
    cost_shadow = contract.evaluation_policy == "synthetic-cost-shadow-training/v1"
    if cost_shadow and screening != SCREEN_POLICY:
        raise ValueError("cost shadow contract requires the versioned exact-zero screen")
    if screening is not None and screening != SCREEN_POLICY:
        raise ValueError("unsupported screening policy")
    receipt = None
    cost_labels = None
    if screening is not None and (pruning_enabled or cost_shadow):
        with compiler_events(
            cache,
            catalog,
            contract.dataset_hash,
            contract.instrument_hash,
            contract.code_revision,
            spec,
            start_ns=window.start_ns,
            end_ns=window.end_ns,
        ) as (events, transform_lookup):
            if cost_shadow:
                cost_labels = estimate_labels(
                    events,
                    spec,
                    profile,
                    contract,
                    CostHorizonPolicy(),
                    transform_lookup=transform_lookup,
                )
                if pruning_enabled:
                    receipt = from_summary(
                        cost_labels["signal_count"], cost_labels["signal_sha256"], contract
                    )
            else:
                receipt = screen(
                    iter_bar_signals(events, spec, transform_lookup=transform_lookup), contract
                )
        catalog.verify(contract.dataset_hash, deep=True)
        with Store(Path(root) / "factory.sqlite").transaction() as db:
            reject_quarantined(db, manifest)
        if require_execution_version(contract) != context:
            raise ValueError("execution source changed during screen")
        screen_hash = persist(root, receipt) if receipt is not None else None
        if (
            receipt is not None
            and receipt.decision == "PRUNE_NO_SIGNALS"
            and pruning_enabled
            and audit_cohort is None
        ):
            return {
                "result_kind": "SCREENED_OUT",
                "screen": receipt.model_dump(mode="json"),
                "screen_artifact_hash": screen_hash,
            }
    with compiler_events(
        cache,
        catalog,
        contract.dataset_hash,
        contract.instrument_hash,
        contract.code_revision,
        spec,
        start_ns=window.start_ns,
        end_ns=window.end_ns,
    ) as (events, transform_lookup):
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
    with Store(Path(root) / "factory.sqlite").transaction() as db:
        reject_quarantined(db, manifest)
    result["runtime_provenance"] = context
    if audit_cohort is not None:
        result["frozen_screen_audit_cohort"] = audit_cohort
    if screening is not None and not pruning_enabled:
        result["tier0_pruning_bypassed"] = "PERSISTENT_NATIVE_AUDIT_CIRCUIT_BREAKER"
    if cost_labels is not None:
        result["cost_horizon_labels"] = cost_labels
    if registry is not None:
        if registry.require(contract, profile) != admission:
            raise ValueError("historical admission changed during replay")
        result["input_admission"] = admission
    if receipt is not None:
        result["tier0_screen"] = receipt.model_dump(mode="json")
        if receipt.signal_count == 0 and pruning_enabled:
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
        if any(e.get("reason") == "TIER0_FALSE_NEGATIVE" for e in result["integrity_errors"]):
            from factory.screening.fallback import trip

            trip(Store(Path(root) / "factory.sqlite"), contract, quarantine_hash)
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
