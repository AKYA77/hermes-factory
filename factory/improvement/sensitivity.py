"""Parameter sensitivity reporting for controlled parent-child comparisons.

Sensitivity is descriptive. It reports how training outcomes varied with
controlled parameter changes on the same frozen span. It never ranks, qualifies
or promotes a strategy, and it never reads a protected evaluation window.
"""

from collections import defaultdict
from decimal import Decimal as D
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "improvement-sensitivity/v1"
ATTESTATION = (
    "Report descriptive parameter sensitivity for controlled training comparisons "
    "only; no qualification, ranking or promotion"
)


class SensitivityRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    policy_hash: Hash
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


class Sensitivity:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = SensitivityRequest.model_validate(request)
        rows = self.store.rows(
            """SELECT e.edge_id, e.hypothesis, e.changed_fields_json, e.payload_json,
                      o.status, o.evidence_json
               FROM improvement_edges e
               JOIN improvement_plans p USING(plan_hash)
               JOIN improvement_outcomes o USING(edge_id)
               WHERE p.policy_hash=?
               ORDER BY e.created_at, e.edge_id""",
            (request.policy_hash,),
        )
        if not rows:
            raise ValueError("no retained improvement outcomes for this policy")
        fields = defaultdict(lambda: {"comparisons": 0, "outcomes": defaultdict(int), "deltas": []})
        hypotheses = defaultdict(int)
        for row in rows:
            changed = json.loads(row["changed_fields_json"])
            evidence = json.loads(row["evidence_json"])
            delta = evidence.get("ending_equity_delta")
            key = ",".join(sorted(changed)) if changed else "UNCHANGED"
            entry = fields[key]
            entry["comparisons"] += 1
            entry["outcomes"][row["status"]] += 1
            if delta is not None:
                entry["deltas"].append(D(delta))
            hypotheses[row["hypothesis"]] += 1
        summary = {}
        for key, entry in fields.items():
            deltas = entry["deltas"]
            summary[key] = {
                "comparisons": entry["comparisons"],
                "outcomes": dict(entry["outcomes"]),
                "ending_equity_delta_mean": str(sum(deltas) / len(deltas)) if deltas else None,
                "ending_equity_delta_min": str(min(deltas)) if deltas else None,
                "ending_equity_delta_max": str(max(deltas)) if deltas else None,
            }
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "policy_hash": request.policy_hash,
            "comparisons": len(rows),
            "by_changed_field": summary,
            "hypotheses": dict(hypotheses),
            "independently_validated": False,
            "descriptive_only": True,
            "limitations": [
                "Descriptive sensitivity on one frozen training span per policy",
                "A parameter change is not a causal estimate; correlated settings move together",
                "Small comparison counts cannot support a stability claim",
                "No protected evaluation or holdout window is read",
                "Training-only sensitivity never qualifies, ranks or promotes a strategy",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "sensitivity" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable sensitivity report conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "improvement_sensitivity_reported",
                {"sensitivity_id": identity, "comparisons": len(rows)},
            )
        return body
