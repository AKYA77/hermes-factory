"""Qualified ranking over independently evaluated candidates.

Ranking covers only retained non-synthetic independent evaluations. It applies a
diversity guard on (operator, timeframe) and never promotes a candidate to a
qualified or validated claim.
"""

import json
from decimal import Decimal as D
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import (
    Contract,
    ExperimentContract,
    StrategySpec,
    fingerprint,
    serialize,
)
from factory.data import atomic_bytes
from factory.reporting import metrics
from factory.ranking.qualified import select_diverse

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "independent-qualified-ranking/v1"
ATTESTATION = (
    "Rank retained non-synthetic independent evaluations descriptively only; no "
    "qualification or promotion"
)


class IndependentRankingRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    max_slots: int = Field(default=5, ge=1, le=5)
    per_key_limit: int = Field(default=2, ge=1, le=5)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def bounded(self):
        if self.per_key_limit > self.max_slots:
            raise ValueError("per-key limit cannot exceed the slot count")
        return self


class IndependentRanking:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def _candidates(self):
        rows = self.store.rows(
            "SELECT e.strategy_id, e.status AS experiment_status, e.result_json, "
            "r.evaluation_id, r.result_json AS evaluation_json, r.contract_json "
            "FROM evaluation_results r JOIN experiments e ON e.experiment_hash=r.evaluation_id "
            "ORDER BY r.created_at, r.evaluation_id"
        )
        out = []
        for row in rows:
            evaluation = json.loads(row["evaluation_json"])
            if evaluation.get("synthetic"):
                continue
            contract = ExperimentContract.model_validate_json(row["contract_json"])
            specs = self.store.rows(
                "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (row["strategy_id"],)
            )
            if not specs:
                continue
            spec = StrategySpec.model_validate_json(specs[0]["spec_json"])
            result = json.loads(row["result_json"])
            out.append(
                {
                    "evaluation_id": row["evaluation_id"],
                    "strategy_id": row["strategy_id"],
                    "operator": spec.signal.operator,
                    "timeframe": spec.timeframe,
                    "experiment_status": row["experiment_status"],
                    "metrics": metrics(result["trades"]),
                    "ending_equity": D(str(result["ending_equity"])),
                    "windows": len(contract.windows),
                }
            )
        return out

    def report(self, request):
        request = IndependentRankingRequest.model_validate(request)
        candidates = self._candidates()
        ordered = sorted(
            candidates,
            key=lambda c: (-c["ending_equity"], c["strategy_id"], c["evaluation_id"]),
        )
        selected, skipped, counts = select_diverse(
            ordered, request.max_slots, request.per_key_limit
        )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "evaluations_considered": len(candidates),
            "selected": selected,
            "skipped": skipped,
            "diversity_counts": counts,
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Ranking covers retained non-synthetic independent evaluations only",
                "Diversity is by operator and timeframe only, not by parameter distance",
                "A ranked candidate is not qualified or validated",
                "Pooled equity is not a paired or significance-tested comparison",
                "Protected holdout and regime gates remain separate",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "independent-ranking" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable independent ranking conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "independent_ranking_reported",
                {"ranking_id": identity, "considered": len(candidates)},
            )
        return body
