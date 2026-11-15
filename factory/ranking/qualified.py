"""Diversity-aware qualified candidate selection; never validation.

Selection is a descriptive shortlist guard over an already-ranked candidate
list. It never promotes a candidate to a qualified or validated claim.
"""

from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, StrategySpec, SYMBOLS, fingerprint, serialize
from factory.data import atomic_bytes
from factory.experiments import Store
from factory.reporting import metrics
from factory.simulation.ledger import EXECUTION_VERSION

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "qualified-ranking/v1"
ATTESTATION = (
    "Select a descriptive diversity-aware training shortlist only; no "
    "qualification, ranking promotion or validation"
)


class QualifiedRankingRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    instrument: str
    max_slots: int = Field(default=5, ge=1, le=5)
    per_key_limit: int = Field(default=2, ge=1, le=5)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def known_instrument(self):
        if self.instrument not in SYMBOLS:
            raise ValueError("unknown instrument")
        if self.per_key_limit > self.max_slots:
            raise ValueError("per-key limit cannot exceed the slot count")
        return self


def _candidates(store, instrument):
    rows = store.rows(
        "SELECT * FROM experiments WHERE instrument=? ORDER BY created_at", (instrument,)
    )
    out = []
    for row in rows:
        contract = json.loads(row["contract_json"])
        if contract.get("fill_version") != EXECUTION_VERSION:
            continue
        if contract.get("scenario") != "historical-pessimistic/v1":
            continue
        specs = store.rows(
            "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (row["strategy_id"],)
        )
        if not specs:
            continue
        spec = StrategySpec.model_validate_json(specs[0]["spec_json"])
        result = json.loads(row["result_json"])
        out.append(
            {
                "strategy_id": row["strategy_id"],
                "run_id": row["run_id"],
                "status": row["status"],
                "operator": spec.signal.operator,
                "timeframe": spec.timeframe,
                "metrics": metrics(result["trades"]),
            }
        )
    return out


TIER = {"VALIDATED": 3, "SIMULATED": 2, "INSUFFICIENT_EVIDENCE": 1, "FAILED_CHECKS": 0}


def _order(candidate):
    m = candidate["metrics"]
    return (
        -TIER[candidate["status"]],
        -(m["win_rate"] if m["win_rate"] is not None else -1),
        m["insolvent"],
        m["max_losing_streak"],
        -Decimal(m["ending_balance"]),
        -m["max_winning_streak"],
        candidate["strategy_id"],
    )


def select_diverse(candidates, max_slots=5, per_key_limit=2):
    """Greedy diversity-aware selection over an already-ranked list."""
    selected, skipped = [], []
    counts = Counter()
    for candidate in candidates:
        key = (candidate["operator"], candidate["timeframe"])
        if len(selected) < max_slots and counts[key] < per_key_limit:
            selected.append(candidate)
            counts[key] += 1
        else:
            skipped.append(
                {
                    "strategy_id": candidate["strategy_id"],
                    "operator": candidate["operator"],
                    "timeframe": candidate["timeframe"],
                    "reason": "DIVERSITY_LIMIT" if counts[key] >= per_key_limit else "SLOT_LIMIT",
                }
            )
    return selected, skipped, {f"{key[0]}|{key[1]}": value for key, value in counts.items()}


class QualifiedRanking:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = QualifiedRankingRequest.model_validate(request)
        candidates = sorted(_candidates(self.store, request.instrument), key=_order)
        selected, skipped, counts = select_diverse(
            candidates, request.max_slots, request.per_key_limit
        )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "instrument": request.instrument,
            "max_slots": request.max_slots,
            "per_key_limit": request.per_key_limit,
            "candidates_considered": len(candidates),
            "selected": selected,
            "skipped": skipped,
            "diversity_counts": counts,
            "selection_policy": "tier-then-diversity greedy shortlist",
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Descriptive shortlist over retained training experiments",
                "Diversity is by operator and timeframe only, not by parameter distance",
                "Selection does not qualify, rank for promotion or validate a strategy",
                "Dataset and evaluation-window comparability remains a separate gate",
                "An empty shortlist is valid when no candidate is retained",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "qualified-ranking" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable qualified ranking conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "qualified_ranking_reported",
                {
                    "ranking_id": identity,
                    "instrument": request.instrument,
                    "selected": len(selected),
                },
            )
        return body


def store(root):
    return Store(Path(root) / "factory.sqlite")
