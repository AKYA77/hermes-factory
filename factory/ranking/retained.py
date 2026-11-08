"""Retained rejected candidates; nothing is silently discarded.

Every experiment row is reported with the reason it is or is not eligible for the
leaderboard. A poor training score is retained and visible; a failed
out-of-sample run is not validated and is not discarded either.
"""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, SYMBOLS, fingerprint, serialize
from factory.data import atomic_bytes
from factory.reporting import metrics
from factory.simulation.ledger import EXECUTION_VERSION

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "retained-rejected-candidates/v1"
ATTESTATION = (
    "Retain and report every candidate with its exclusion reason; no silent "
    "discard and no validation of failed out-of-sample runs"
)


class RetainedCandidatesRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    instrument: str
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def known_instrument(self):
        if self.instrument not in SYMBOLS:
            raise ValueError("unknown instrument")
        return self


class RetainedCandidates:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = RetainedCandidatesRequest.model_validate(request)
        rows = self.store.rows(
            "SELECT * FROM experiments WHERE instrument=? ORDER BY created_at, run_id",
            (request.instrument,),
        )
        retained = []
        for row in rows:
            contract = json.loads(row["contract_json"])
            result = json.loads(row["result_json"])
            reasons = []
            if contract.get("fill_version") != EXECUTION_VERSION:
                reasons.append("EXECUTION_VERSION_MISMATCH")
            if contract.get("scenario") != "historical-pessimistic/v1":
                reasons.append("NON_PESSIMISTIC_SCENARIO")
            if row["status"] == "FAILED_CHECKS":
                reasons.append("FAILED_CHECKS")
            elif row["status"] == "INSUFFICIENT_EVIDENCE":
                reasons.append("INSUFFICIENT_EVIDENCE")
            retained.append(
                {
                    "strategy_id": row["strategy_id"],
                    "run_id": row["run_id"],
                    "status": row["status"],
                    "exclusion_reasons": reasons,
                    "leaderboard_eligible": not reasons,
                    "synthetic": result.get("synthetic"),
                    "metrics": metrics(result["trades"]),
                }
            )
        eligible = [entry for entry in retained if entry["leaderboard_eligible"]]
        rejected = [entry for entry in retained if not entry["leaderboard_eligible"]]
        counts = {}
        for entry in rejected:
            for reason in entry["exclusion_reasons"]:
                counts[reason] = counts.get(reason, 0) + 1
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "instrument": request.instrument,
            "execution_version": EXECUTION_VERSION,
            "total": len(retained),
            "eligible": len(eligible),
            "retained_rejected": len(rejected),
            "exclusion_reason_counts": counts,
            "candidates": retained,
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Every candidate row is retained and reported, never discarded",
                "A poor training score stays visible with its metrics",
                "A failed out-of-sample run is not validated and is not dropped",
                "Exclusion reasons describe leaderboard eligibility only",
                "Dataset and evaluation-window comparability remains unfinished",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "retained-candidates" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable retained candidates conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "retained_candidates_reported",
                {
                    "report_id": identity,
                    "instrument": request.instrument,
                    "retained": len(retained),
                    "rejected": len(rejected),
                },
            )
        return body
