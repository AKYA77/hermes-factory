"""Frozen comparability contracts and selection-bias reporting.

Comparability states whether frozen screening cohorts share evaluation
semantics. It never authorizes pooling screening observations into a
qualification, ranking or strategy claim, and it always reports how much of the
sampled frame was actually observed natively.
"""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "screen-comparability/v1"
MAX_COHORTS = 16
ATTESTATION = (
    "Compare frozen screening cohorts for evaluation-semantics comparability only; "
    "no pooling into qualification, ranking or strategy evidence"
)


class ComparabilityRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    cohort_ids: tuple[Hash, ...] = Field(min_length=2, max_length=MAX_COHORTS)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.cohort_ids)) != len(self.cohort_ids):
            raise ValueError("duplicate cohort in comparability request")
        object.__setattr__(self, "cohort_ids", tuple(sorted(self.cohort_ids)))
        return self


SUBJECT_KEYS = (
    "instrument_hash",
    "operator",
    "timeframe",
    "confirmations",
    "scenario",
    "code_revision",
    "policy_hash",
)


class Comparability:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def _body(self, identity):
        rows = self.store.rows(
            "SELECT body_json FROM screen_cohorts WHERE cohort_id=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown screen cohort")
        body = json.loads(rows[0]["body_json"])
        if fingerprint(body) != identity:
            raise ValueError("screen cohort identity mismatch")
        return body

    def describe(self, identity):
        from factory.screening.cohorts import Cohorts

        body = self._body(identity)
        subject = {k: body["subject"].get(k) for k in SUBJECT_KEYS}
        report = Cohorts(self.store, self.root).report(identity)
        return {
            "cohort_id": identity,
            "schema_version": body["schema_version"],
            "historical": bool(body.get("historical")),
            "subject": subject,
            "frame_members": len(body["frame"]),
            "selected": len(body["selected"]),
            "selected_observed": report["native_observed"],
            "false_negatives": report["false_negatives"],
            "known_counterexamples": report["known_counterexamples"],
            "approximate_pruning_authorized": report["approximate_pruning_authorized"],
            "source_current": report["source_current"],
        }

    def compare(self, request):
        request = ComparabilityRequest.model_validate(request)
        descriptions = [self.describe(identity) for identity in request.cohort_ids]
        comparable = []
        for index, left in enumerate(descriptions):
            for right in descriptions[index + 1 :]:
                differences = [
                    key for key in SUBJECT_KEYS if left["subject"][key] != right["subject"][key]
                ]
                comparable.append(
                    {
                        "left": left["cohort_id"],
                        "right": right["cohort_id"],
                        "comparable": not differences,
                        "differences": differences,
                    }
                )
        effective = set()
        selected = set()
        for identity in request.cohort_ids:
            body = self._body(identity)
            effective.update(f["effective_hash"] for f in body["frame"])
            selected.update(body["selected"])
        observed = {d["cohort_id"]: d["selected_observed"] for d in descriptions}
        observed_total = sum(observed.values())
        unobserved = len(selected) - observed_total
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "cohorts": descriptions,
            "pairwise": comparable,
            "all_comparable": all(row["comparable"] for row in comparable),
            "selection_bias": {
                "distinct_effective_experiments": len(effective),
                "selected_for_native_audit": len(selected),
                "selected_and_observed": observed_total,
                "selected_but_unobserved": unobserved,
                "unselected_frame_members": len(effective) - len(selected),
                "selection_ratio": (len(selected) / len(effective)) if effective else None,
            },
            "pooled_claim_authorized": False,
            "approximate_pruning_authorized": False,
            "limitations": [
                "Comparability is evaluation-semantics only; it is not strategy validation or ranking qualification",
                "Unselected frame members have no native observation and cannot support a false-negative estimate",
                "Selection was fixed before outcomes, but correlated strategies and labels are not IID",
                "Descriptive screening statistics must never be pooled into a performance or qualification claim",
                "Native source or code changes require new cohorts; reused identities add no independent observations",
            ],
        }
        identity = fingerprint(body)
        path = self.root / "artifacts" / "comparability" / (identity + ".json")
        encoded = serialize(body).encode()
        if path.exists() and path.read_bytes() != encoded:
            raise ValueError("immutable comparability report conflict")
        atomic_bytes(path, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "screen_comparability_reported",
                {"comparability_id": identity, "cohorts": len(descriptions)},
            )
        return body
