"""Instrument-specific all-candidate views; synthetic results cannot be validated."""

import json
from decimal import Decimal
from factory.contracts import SYMBOLS
from factory.reporting import metrics
from factory.simulation.ledger import EXECUTION_VERSION


def leaderboard(store, symbol, validated_only=False, execution_version=EXECUTION_VERSION):
    if symbol not in SYMBOLS:
        raise ValueError("unknown instrument")
    rows = store.rows(
        "SELECT * FROM experiments WHERE instrument=? ORDER BY created_at DESC", (symbol,)
    )
    candidates = {}
    excluded = 0
    for row in rows:
        contract = json.loads(row["contract_json"])
        if contract["fill_version"] != execution_version:
            excluded += 1
            continue
        if validated_only and execution_version != EXECUTION_VERSION:
            continue
        if contract["scenario"] != "historical-pessimistic/v1":
            continue
        if validated_only and row["status"] != "VALIDATED":
            continue
        if row["strategy_id"] in candidates:
            continue
        result = json.loads(row["result_json"])
        candidates[row["strategy_id"]] = {
            "strategy_id": row["strategy_id"],
            "run_id": row["run_id"],
            "status": row["status"],
            "synthetic": result["synthetic"],
            "metrics": metrics(result["trades"]),
        }
    tier = {"VALIDATED": 3, "SIMULATED": 2, "INSUFFICIENT_EVIDENCE": 1, "FAILED_CHECKS": 0}

    def order(c):
        m = c["metrics"]
        return (
            -tier[c["status"]],
            -(m["win_rate"] if m["win_rate"] is not None else -1),
            m["insolvent"],
            m["max_losing_streak"],
            -Decimal(m["ending_balance"]),
            -m["max_winning_streak"],
            c["strategy_id"],
        )

    return {
        "instrument": symbol,
        "ranking_policy": "v1-development",
        "candidates": sorted(candidates.values(), key=order)[:5],
        "max_slots": 5,
        "execution_version": execution_version,
        "excluded_other_execution_runs": excluded,
        "legacy_evidence": execution_version != EXECUTION_VERSION,
        "comparison_limits": "Dataset and evaluation-window comparability remains unfinished.",
        "warning": "Independent evidence promotion is not implemented; no validated claim.",
    }
