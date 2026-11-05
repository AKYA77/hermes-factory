"""Frozen training screen audits, never independent strategy qualification.

Calibration can expose a bad approximation; it cannot grant pruning permission.
Native audit selection is fixed before outcomes, with a retained sampling frame.
"""

import json
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import (
    Contract,
    ExperimentContract,
    InstrumentSpec,
    StrategySpec,
    fingerprint,
    serialize,
)
from factory.data import Catalog, sha256
from factory.provenance import execution_revision
from factory.screening.labels import CostHorizonPolicy
from factory.validation import wilson

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ATTESTATION = "Freeze this training-only screening cohort before native audit outcomes; no validation or pruning authority"


class CohortRequest(Contract):
    schema_version: Literal["frozen-screen-cohort/v1"] = "frozen-screen-cohort/v1"
    calibration_experiments: tuple[Hash, ...] = Field(min_length=1, max_length=128)
    prospective_job_ids: tuple[Annotated[str, Field(min_length=1, max_length=64)], ...] = Field(
        min_length=1, max_length=256
    )
    audit_sample_count: int = Field(ge=1, le=128, strict=True)
    seed: int = Field(ge=0, strict=True)
    policy: CostHorizonPolicy = Field(default_factory=CostHorizonPolicy)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def unique_members(self):
        if len(set(self.calibration_experiments)) != len(self.calibration_experiments) or len(
            set(self.prospective_job_ids)
        ) != len(self.prospective_job_ids):
            raise ValueError("duplicate cohort member")
        if self.audit_sample_count > len(self.prospective_job_ids):
            raise ValueError("audit sample exceeds frame")
        object.__setattr__(
            self, "calibration_experiments", tuple(sorted(self.calibration_experiments))
        )
        object.__setattr__(self, "prospective_job_ids", tuple(sorted(self.prospective_job_ids)))
        object.__setattr__(
            self, "calibration_experiments", tuple(sorted(self.calibration_experiments))
        )
        object.__setattr__(self, "prospective_job_ids", tuple(sorted(self.prospective_job_ids)))
        return self


def subject(value):
    return {
        k: value[k]
        for k in (
            "instrument_hash",
            "operator",
            "timeframe",
            "confirmations",
            "scenario",
            "code_revision",
            "policy_hash",
        )
    }


class Cohorts:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def verify_native(self, body):
        path = self.root / "artifacts" / (body["experiment_hash"] + ".json")
        try:
            if path.is_symlink() or sha256(path) != body["native_artifact_hash"]:
                raise ValueError("calibration/audit native artifact integrity")
        except OSError as exc:
            raise ValueError("calibration/audit native artifact unavailable") from exc

    def freeze(self, request):
        request = CohortRequest.model_validate(request)
        revision = execution_revision()
        policy_hash = fingerprint(request.policy)
        if policy_hash != fingerprint(CostHorizonPolicy()):
            raise ValueError("cohort policy differs from the current worker estimator")
        with self.store.transaction() as db:
            prior = db.execute(
                "SELECT cohort_id FROM screen_cohorts WHERE json_extract(body_json,'$.request_hash')=?",
                (fingerprint(request),),
            ).fetchone()
            if prior:
                return prior[0]
            calibration = []
            for experiment in sorted(request.calibration_experiments):
                row = db.execute(
                    "SELECT body_json FROM cost_label_audits WHERE experiment_hash=?", (experiment,)
                ).fetchone()
                if row is None:
                    raise ValueError("calibration requires retained native audit")
                body = json.loads(row[0])
                if body["code_revision"] != revision or body["policy_hash"] != policy_hash:
                    raise ValueError("stale or incompatible calibration")
                self.verify_native(body)
                calibration.append(body)
            comparison = subject(calibration[0])
            if any(subject(c) != comparison for c in calibration):
                raise ValueError("calibration subjects differ")
            latest = max(int(w["end_ns"]) for c in calibration for w in c["windows"])
            frame = []
            seen = set(request.calibration_experiments)
            effective = set()
            for identity in sorted(request.prospective_job_ids):
                row = db.execute("SELECT * FROM jobs WHERE job_id=?", (identity,)).fetchone()
                if (
                    row is None
                    or row["kind"] != "research"
                    or row["state"] not in ("QUEUED", "FAILED_RETRYABLE")
                    or row["attempts"]
                ):
                    raise ValueError("audit membership must be frozen before any native attempt")
                payload = json.loads(row["payload"])
                from factory.screening import SCREEN_POLICY

                if payload.get("screening") != SCREEN_POLICY:
                    raise ValueError("cohort requires the explicit existing screen marker")
                contract = ExperimentContract.model_validate(payload["contract"])
                spec = StrategySpec.model_validate(payload["strategy"])
                profile = InstrumentSpec.model_validate(payload["profile"])
                if (
                    not profile.synthetic
                    or contract.evaluation_policy != "synthetic-cost-shadow-training/v1"
                ):
                    raise ValueError(
                        "v1 cohorts require explicit synthetic cost-shadow training; historical calibration is not implemented"
                    )
                if len(contract.windows) != 1 or contract.windows[0].role != "train_only":
                    raise ValueError("screen calibration is training-only")
                if (
                    contract.code_revision != revision
                    or spec.strategy_hash != contract.strategy_hash
                    or fingerprint(profile) != contract.instrument_hash
                ):
                    raise ValueError("cohort contract identity mismatch")
                context = {
                    "instrument_hash": contract.instrument_hash,
                    "operator": spec.signal.operator,
                    "timeframe": spec.timeframe,
                    "confirmations": list(spec.confirmations),
                    "scenario": contract.scenario,
                    "code_revision": revision,
                    "policy_hash": policy_hash,
                }
                if context != comparison:
                    raise ValueError("prospective and calibration subjects differ")
                if contract.windows[0].start_ns < latest + 86400 * 10**9:
                    raise ValueError(
                        "prospective audit requires separate later training with 24h label embargo"
                    )
                experiment = contract.experiment_hash
                if (
                    experiment in seen
                    or db.execute(
                        "SELECT 1 FROM experiments WHERE experiment_hash=?", (experiment,)
                    ).fetchone()
                    or db.execute(
                        "SELECT 1 FROM screen_cohort_members WHERE experiment_hash=? AND role='prospective'",
                        (experiment,),
                    ).fetchone()
                ):
                    raise ValueError("cohort outcome already seen or member already frozen")
                # Seed changes alone are not independent candidate evidence.
                key = fingerprint(
                    {k: v for k, v in contract.model_dump(mode="json").items() if k != "seed"}
                )
                if (
                    key in effective
                    or db.execute(
                        "SELECT 1 FROM screen_cohort_effective_inputs WHERE effective_hash=?",
                        (key,),
                    ).fetchone()
                ):
                    raise ValueError(
                        "duplicate effective experiment in sampling frame or prior cohort"
                    )
                seen.add(experiment)
                effective.add(key)
                catalog = Catalog(self.root / "catalog")
                manifest = catalog.verify(contract.dataset_hash, deep=True)
                if (
                    manifest["instrument"] != profile.instrument
                    or manifest["provenance"].get("synthetic") is not True
                ):
                    raise ValueError("cohort source/profile mismatch")
                from factory.data.versions import reject_quarantined
                from factory.exploration.discovery import require_training_scope

                reject_quarantined(db, manifest)
                require_training_scope(
                    db, SimpleNamespace(profile=profile, window=contract.windows[0])
                )
                frame.append(
                    {
                        "job_id": identity,
                        "experiment_hash": experiment,
                        "payload_sha256": fingerprint(payload),
                        "effective_hash": key,
                        "contract": contract.model_dump(mode="json"),
                    }
                )
            selected = set(
                f["experiment_hash"]
                for f in sorted(
                    frame,
                    key=lambda f: fingerprint(
                        {
                            "experiment": f["experiment_hash"],
                            "seed": request.seed,
                            "policy": policy_hash,
                        }
                    ),
                )[: request.audit_sample_count]
            )
            body = {
                "schema_version": request.schema_version,
                "request_hash": fingerprint(request),
                "request": request.model_dump(mode="json"),
                "subject": comparison,
                "calibration": calibration,
                "frame": frame,
                "selected": sorted(selected),
                "scope": "Explicit frozen training sampling frame; not full-universe independence or strategy validation",
                "approximate_pruning_authorized": False,
            }
            cohort = fingerprint(body)
            if db.execute("SELECT 1 FROM screen_cohorts WHERE cohort_id=?", (cohort,)).fetchone():
                return cohort
            db.execute(
                "INSERT INTO screen_cohorts VALUES(?,?,?)", (cohort, serialize(body), time.time())
            )
            db.executemany(
                "INSERT INTO screen_cohort_members VALUES(?,?,?,?,?)",
                [(cohort, c["experiment_hash"], "calibration", None, 0) for c in calibration]
                + [
                    (
                        cohort,
                        f["experiment_hash"],
                        "prospective",
                        f["job_id"],
                        int(f["experiment_hash"] in selected),
                    )
                    for f in frame
                ],
            )
            db.executemany(
                "INSERT INTO screen_cohort_effective_inputs VALUES(?,?,?)",
                [(f["effective_hash"], cohort, f["experiment_hash"]) for f in frame],
            )
            self.store._audit(
                db,
                request.authorized_by,
                "screen_cohort_frozen",
                {"cohort_id": cohort, "frame": len(frame), "selected": len(selected)},
            )
            return cohort

    def report(self, identity):
        rows = self.store.rows(
            "SELECT body_json FROM screen_cohorts WHERE cohort_id=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown screen cohort")
        body = json.loads(rows[0]["body_json"])
        if fingerprint(body) != identity:
            raise ValueError("screen cohort identity mismatch")
        for calibration in body["calibration"]:
            self.verify_native(calibration)
        observations = []
        for experiment in body["selected"]:
            row = self.store.rows(
                "SELECT body_json FROM cost_label_audits WHERE experiment_hash=?", (experiment,)
            )
            if row:
                observation = json.loads(row[0]["body_json"])
                self.verify_native(observation)
                observations.append(observation)
        rejected = [o for o in observations if o["prospective_cost_rejection"]]
        false = sum(o["observed_false_negative"] for o in rejected)
        counterexamples = sum(o["observed_false_negative"] for o in body["calibration"]) + false
        return {
            "cohort_id": identity,
            "source_current": body["subject"]["code_revision"] == execution_revision(),
            "frozen": body,
            "native_observed": len(observations),
            "selected_count": len(body["selected"]),
            "audit_complete": len(observations) == len(body["selected"]),
            "prospective_rejections_audited": len(rejected),
            "false_negatives": false,
            "descriptive_wilson_95": wilson(false, len(rejected)) if rejected else None,
            "known_counterexamples": counterexamples,
            "shortlist_policy": "ALL_CANDIDATES_TO_NATIVE_EXCEPT_EXISTING_EXACT_ZERO_RULE",
            "approximate_pruning_authorized": False,
            "disposition": "ALL_NATIVE_FALLBACK_COUNTEREXAMPLE"
            if counterexamples
            else "REPORT_ONLY_NO_APPROXIMATE_PRUNING",
            "limitations": [
                "Wilson interval is descriptive for the frozen frame; correlated strategies/labels are not IID",
                "No OOS, holdout, ranking qualification or independent strategy evidence",
                "Native source/code changes require a new cohort; reused identities do not add independent observations",
            ],
        }


def selected_cohort(store, contract):
    rows = store.rows(
        "SELECT cohort_id FROM screen_cohort_members WHERE experiment_hash=? AND role='prospective' AND selected=1",
        (contract.experiment_hash,),
    )
    return rows[0]["cohort_id"] if rows else None
