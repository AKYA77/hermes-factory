"""Frozen-window replay evaluation. No tuning or holdout reuse permitted here."""

from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, fingerprint
from factory.data import Catalog
from factory.diagnostics import diagnose_trade
from factory.reporting import metrics
from factory.simulation.runner import replay
from factory.simulation.ledger import require_execution_version
from factory.strategies import compile_signals


def evaluate(root, payload):
    contract = ExperimentContract.model_validate(payload["contract"])
    require_execution_version(contract)
    spec = StrategySpec.model_validate(payload["strategy"])
    profile = InstrumentSpec.model_validate(payload["profile"])
    if (
        spec.strategy_hash != contract.strategy_hash
        or fingerprint(profile) != contract.instrument_hash
    ):
        raise ValueError("contract mismatch")
    if profile.quote_currency != "USD":
        raise ValueError("dated currency conversion unsupported")
    catalog = Catalog(root)
    manifest = catalog.verify(contract.dataset_hash)
    if manifest["instrument"] != spec.instrument or profile.instrument != spec.instrument:
        raise ValueError("instrument mismatch")
    if not profile.synthetic or not manifest["provenance"].get("synthetic"):
        raise ValueError(
            "HISTORICAL_EVALUATION_BLOCKED: verified profiles and evaluation gates required"
        )
    quotes = list(catalog.read(contract.dataset_hash))
    # Compile once on chronological data. All operators are past-only. Signals are
    # filtered by their available_at time; previous bars supply warm-up without labels.
    signals = compile_signals(quotes, spec)
    results = []
    for window in contract.windows:
        window_quotes = [q for q in quotes if window.start_ns <= q.event_ts_utc_ns < window.end_ns]
        window_signals = [
            s for s in signals if window.start_ns <= s["available_at"] < window.end_ns
        ]
        if not window_quotes:
            results.append(
                {"window": window.model_dump(), "status": "DATA_UNAVAILABLE", "metrics": None}
            )
            continue
        result = replay(
            window_quotes,
            profile,
            spec,
            window_signals,
            contract.scenario == "historical-pessimistic/v1",
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
    return {
        "contract_hash": contract.experiment_hash,
        "windows": results,
        "synthetic": profile.synthetic,
        "status": "INSUFFICIENT_EVIDENCE",
        "selection_policy": "fixed spec; no optimization on OOS",
    }
