"""Frozen-window replay evaluation. No tuning or holdout reuse permitted here."""

from itertools import chain

from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, fingerprint
from factory.data import Catalog
from factory.diagnostics import diagnose_trade
from factory.reporting import metrics
from factory.simulation.runner import replay
from factory.simulation.ledger import require_execution_version
from factory.strategies import iter_bar_signals
from factory.features.disk import BarCache
from pathlib import Path


def evaluate(root, payload):
    contract = ExperimentContract.model_validate(payload["contract"])
    context = require_execution_version(contract)
    spec = StrategySpec.model_validate(payload["strategy"])
    profile = InstrumentSpec.model_validate(payload["profile"])
    if (
        spec.strategy_hash != contract.strategy_hash
        or fingerprint(profile) != contract.instrument_hash
    ):
        raise ValueError("contract mismatch")
    catalog = Catalog(root)
    manifest = catalog.verify(contract.dataset_hash, deep=True)
    if manifest["instrument"] != spec.instrument or profile.instrument != spec.instrument:
        raise ValueError("instrument mismatch")
    if not profile.synthetic or not manifest["provenance"].get("synthetic"):
        raise ValueError(
            "HISTORICAL_EVALUATION_BLOCKED: verified profiles and evaluation gates required"
        )
    from factory.experiments import Store
    from factory.validation.access import evaluation_use

    store = Store(Path(root).parent / "factory.sqlite")
    with store.transaction() as db:
        evaluation_use(db, profile, contract, manifest, payload)
    results = []
    cache = BarCache(Path(root).parent / "cache" / "evaluation-bars")
    for window in contract.windows:
        # Past-only warm-up, with bounded re-reads. Neither labels nor future bars
        # enter signal construction. Each simulation retains separate $20 equity.
        window_quotes = catalog.read(
            contract.dataset_hash, start_ns=window.start_ns, end_ns=window.end_ns
        )
        first = next(window_quotes, None)
        if first is None:
            results.append(
                {"window": window.model_dump(), "status": "DATA_UNAVAILABLE", "metrics": None}
            )
            continue
        with cache.events(
            catalog,
            contract.dataset_hash,
            contract.instrument_hash,
            contract.code_revision,
            (spec.timeframe, *spec.confirmations),
            end_ns=window.end_ns,
        ) as events:
            window_signals = (
                s
                for s in iter_bar_signals(events, spec)
                if window.start_ns <= s["available_at"] < window.end_ns
            )
            result = replay(
                chain((first,), window_quotes),
                profile,
                spec,
                window_signals,
                contract.scenario == "historical-pessimistic/v1",
                inline_paths=False,
                dataset_hash=contract.dataset_hash,
            )
        if result["integrity_errors"]:
            raise ValueError("EXECUTION_CONTRACT_MISMATCH")
        result["diagnostics"] = [diagnose_trade(t, profile.tick_size) for t in result["trades"]]
        results.append(
            {
                "window": window.model_dump(),
                "status": "INSUFFICIENT_EVIDENCE",
                "metrics": metrics(result["trades"]),
                "replay": result,
                "warnings": [
                    "window resets equity to $20",
                    "boundary-crossing open trades censored",
                    "not WFO parameter refitting",
                    "no automatic validated promotion",
                ],
            }
        )
    catalog.verify(contract.dataset_hash, deep=True)
    if require_execution_version(contract) != context:
        raise ValueError("execution source changed during evaluation")
    return {
        "managed_holdout": {
            "holdout_id": payload.get("holdout_id"),
            "independent_observation_id": payload.get("holdout_authorization"),
            "state": "HOLDOUT_CONSUMED"
            if payload.get("holdout_authorization")
            else "UNCONTROLLED_EXPLORATORY_EVALUATION",
            "repeat_does_not_add_independent_evidence": True,
        },
        "contract_hash": contract.experiment_hash,
        "runtime_provenance": context,
        "windows": results,
        "synthetic": profile.synthetic,
        "status": "INSUFFICIENT_EVIDENCE",
        "selection_policy": "fixed spec; no optimization on OOS",
    }
