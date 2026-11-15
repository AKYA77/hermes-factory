"""Global candidate-selection funnel over retained evidence.

The funnel is descriptive. It counts how many distinct effective candidates were
considered, selected for native audit, observed, and promoted. It never
qualifies, ranks or promotes a strategy, and it never reinterprets a protected
evaluation.
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "selection-funnel/v1"
ATTESTATION = (
    "Report a descriptive global candidate-selection funnel only; no "
    "qualification, ranking or promotion"
)


class SelectionFunnelRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


class SelectionFunnel:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = SelectionFunnelRequest.model_validate(request)

        def count(sql, params=()):
            rows = self.store.rows(sql, params)
            return list(rows[0].values())[0]

        trials = count("SELECT COUNT(*) FROM search_trials")
        distinct_trials = count(
            "SELECT COUNT(DISTINCT json_extract(spec_json,'$.signal.lookback') "
            "|| '|' || json_extract(spec_json,'$.timeframe')) FROM search_trials"
        )
        effective = count(
            "SELECT COUNT(DISTINCT effective_hash) FROM screen_cohort_effective_inputs"
        )
        selected = count(
            "SELECT COUNT(*) FROM screen_cohort_members WHERE role='prospective' AND selected=1"
        )
        observed = count(
            "SELECT COUNT(DISTINCT m.experiment_hash) FROM screen_cohort_members m "
            "JOIN cost_label_audits a ON a.experiment_hash=m.experiment_hash "
            "WHERE m.role='prospective' AND m.selected=1"
        )
        promoted = count(
            "SELECT COUNT(*) FROM improvement_outcomes WHERE status='TRAIN_IMPROVED_ONLY'"
        )
        confirmed = count(
            "SELECT COUNT(*) FROM improvement_outcomes o "
            "JOIN improvement_edges e USING(edge_id) "
            "WHERE o.status='TRAIN_IMPROVED_ONLY'"
        )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "search_trials": trials,
            "distinct_trial_configurations": distinct_trials,
            "distinct_effective_cohort_candidates": effective,
            "selected_for_native_audit": selected,
            "selected_and_observed": observed,
            "training_promotions": promoted,
            "promotions_with_retained_edges": confirmed,
            "funnel_complete": effective > 0 and observed == selected,
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Descriptive funnel over retained evidence in this state",
                "Counts are not independent observations; correlated candidates overlap",
                "A promotion is a training-only label, not independent validation",
                "The funnel never qualifies, ranks or promotes a strategy",
                "Global regime and source validation remain separate gates",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "selection-funnel" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable selection funnel conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "selection_funnel_reported",
                {
                    "funnel_id": identity,
                    "effective": effective,
                    "selected": selected,
                    "observed": observed,
                },
            )
        return body
