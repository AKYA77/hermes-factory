"""Independent confirmation of controlled training improvements.

A `TRAIN_IMPROVED_ONLY` outcome is a training claim. Confirmation binds it to a
retained independent evaluation that used a disjoint window, without ever
reading or reinterpreting the protected evaluation itself.
"""

from decimal import Decimal as D
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, ExperimentContract, fingerprint, serialize
from factory.data import atomic_bytes, sha256

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "improvement-confirmation/v1"
ATTESTATION = (
    "Bind a training improvement to a retained independent evaluation only; "
    "no qualification, ranking or promotion"
)


class ConfirmationRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    edge_id: Hash
    evaluation_id: Hash
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


def _overlaps(left, right):
    return left[0] < right[1] and right[0] < left[1]


class Confirmation:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def _evaluation(self, evaluation_id):
        rows = self.store.rows(
            "SELECT contract_json,result_json,artifact_hash FROM evaluation_results WHERE evaluation_id=?",
            (evaluation_id,),
        )
        if not rows:
            raise ValueError("unknown independent evaluation")
        row = rows[0]
        contract = ExperimentContract.model_validate_json(row["contract_json"])
        artifact = self.root / "artifacts" / "evaluations" / (evaluation_id + ".json")
        if (
            sha256(artifact) != row["artifact_hash"]
            or fingerprint(json.loads(row["result_json"])) != row["artifact_hash"]
        ):
            raise ValueError("independent evaluation artifact integrity mismatch")
        return contract, json.loads(row["result_json"]), row["artifact_hash"]

    def confirm(self, request):
        request = ConfirmationRequest.model_validate(request)
        edges = self.store.rows(
            """SELECT e.edge_id, e.child_experiment_hash, e.payload_json, o.status, o.evidence_json
               FROM improvement_edges e JOIN improvement_outcomes o USING(edge_id)
               WHERE e.edge_id=?""",
            (request.edge_id,),
        )
        if not edges:
            raise ValueError("unknown improvement edge or no retained outcome")
        edge = edges[0]
        if edge["status"] != "TRAIN_IMPROVED_ONLY":
            raise ValueError("only a TRAIN_IMPROVED_ONLY outcome requires confirmation")
        payload = json.loads(edge["payload_json"])
        child = ExperimentContract.model_validate(payload["contract"])
        evaluation, evaluation_result, evaluation_hash = self._evaluation(request.evaluation_id)
        if evaluation.experiment_hash == child.experiment_hash:
            raise ValueError("an evaluation cannot confirm its own training experiment")
        child_windows = [(w.start_ns, w.end_ns) for w in child.windows]
        evaluation_windows = [(w.start_ns, w.end_ns) for w in evaluation.windows]
        overlap = [
            {"training": list(a), "evaluation": list(b)}
            for a in child_windows
            for b in evaluation_windows
            if _overlaps(a, b)
        ]
        if overlap:
            raise ValueError("independent evaluation overlaps the training window")
        if evaluation.dataset_hash != child.dataset_hash:
            raise ValueError("independent evaluation must use the same admitted canonical dataset")
        marked = evaluation_result.get("ending_equity")
        positive = marked is not None and D(str(marked)) > D(
            str(payload["contract"].get("initial_equity", "0"))
        )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "edge_id": request.edge_id,
            "child_experiment_hash": child.experiment_hash,
            "training_outcome": edge["status"],
            "evaluation_id": request.evaluation_id,
            "evaluation_artifact_hash": evaluation_hash,
            "training_windows": [list(w) for w in child_windows],
            "evaluation_windows": [list(w) for w in evaluation_windows],
            "windows_disjoint": True,
            "same_admitted_dataset": True,
            "evaluation_positive_marked_equity": positive,
            "confirmed": bool(positive),
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Confirmation binds a training improvement to one independent evaluation",
                "A positive evaluation is not qualification, ranking or promotion",
                "Correlated settings and overlapping market conditions are not independent",
                "Only the disjoint window is checked; the protected evaluation is not reinterpreted",
                "Independent confirmation does not satisfy global regime or source validation",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "confirmations" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable confirmation conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "improvement_confirmation_recorded",
                {
                    "confirmation_id": identity,
                    "edge_id": request.edge_id,
                    "evaluation_id": request.evaluation_id,
                    "confirmed": body["confirmed"],
                },
            )
        return body
