"""Improvement lineage reconstruction from immutable plans, edges and outcomes.

Lineage is descriptive. It reconstructs the retained parent-to-child tree for one
improvement policy. It never qualifies, ranks or promotes a strategy, and it
never reads a protected evaluation or holdout window.
"""

from collections import Counter
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "improvement-lineage/v1"
ATTESTATION = (
    "Reconstruct retained training improvement lineage only; no qualification, ranking or promotion"
)


class LineageRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    policy_hash: Hash
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


class Lineage:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = LineageRequest.model_validate(request)
        plans = self.store.rows(
            """SELECT plan_hash, parent_run_id, evidence_json, generation_cpu_seconds
               FROM improvement_plans WHERE policy_hash=? ORDER BY created_at, plan_hash""",
            (request.policy_hash,),
        )
        if not plans:
            raise ValueError("no retained improvement plans for this policy")
        parents = []
        statuses = Counter()
        children_total = 0
        for plan in plans:
            edges = self.store.rows(
                """SELECT e.edge_id, e.child_strategy_hash, e.child_experiment_hash,
                          e.hypothesis, e.changed_fields_json, e.payload_json,
                          o.status, o.evidence_json
                   FROM improvement_edges e
                   LEFT JOIN improvement_outcomes o USING(edge_id)
                   WHERE e.plan_hash=? ORDER BY e.created_at, e.edge_id""",
                (plan["plan_hash"],),
            )
            children = []
            for edge in edges:
                status = edge["status"] or "PENDING"
                statuses[status] += 1
                changed = json.loads(edge["changed_fields_json"])
                payload = json.loads(edge["payload_json"])
                children.append(
                    {
                        "edge_id": edge["edge_id"],
                        "child_strategy_hash": edge["child_strategy_hash"],
                        "child_experiment_hash": edge["child_experiment_hash"],
                        "hypothesis": edge["hypothesis"],
                        "changed_fields": changed,
                        "status": status,
                        "training_only": True,
                        "parameter_summary": {
                            key: payload.get("strategy", {}).get(key)
                            for key in ("timeframe", "stop_ticks")
                        },
                    }
                )
            children_total += len(children)
            parents.append(
                {
                    "plan_hash": plan["plan_hash"],
                    "parent_run_id": plan["parent_run_id"],
                    "generation_cpu_seconds": plan["generation_cpu_seconds"],
                    "children": children,
                }
            )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "policy_hash": request.policy_hash,
            "plans": len(plans),
            "parents": len({p["parent_run_id"] for p in parents}),
            "children": children_total,
            "outcome_statuses": dict(statuses),
            "lineage": parents,
            "descriptive_only": True,
            "independently_validated": False,
            "limitations": [
                "Reconstructs retained training improvement lineage for one policy",
                "A child marked TRAIN_IMPROVED_ONLY is not independently validated",
                "Correlated settings move together, so changed fields are not causal",
                "No protected evaluation or holdout window is read",
                "Lineage never ranks, qualifies or promotes a strategy",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "lineage" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable lineage report conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "improvement_lineage_reported",
                {"lineage_id": identity, "plans": len(plans), "children": children_total},
            )
        return body
