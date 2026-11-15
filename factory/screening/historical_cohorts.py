"""Historical prospective calibration cohorts; never approximate pruning.

Version 2 binds reviewed historical admission, exact profile/data/code/training
windows and an explicit no-pruning attestation before any prospective native
outcome exists. Generated-only v1 identities and restrictions are unchanged.

Calibration can expose a bad approximation; it cannot grant pruning permission.
Selection is fixed before outcomes and a cheap proxy never becomes an
authoritative matching engine.
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
from factory.data.admission import InputRegistry, admission_identity
from factory.exploration.discovery import require_training_scope
from factory.provenance import execution_revision
from factory.screening.labels import CostHorizonPolicy
from factory.validation import wilson

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
HISTORICAL_ATTESTATION = (
    "Freeze this historical training-only calibration cohort before prospective native "
    "outcomes; reviewed admission only, no approximate pruning or validation authority"
)
EMBARGO_NS = 86400 * 10**9
HISTORICAL_TRAINING_POLICY = "historical-training/v1"


class HistoricalCalibrationPolicy(Contract):
    """Immutable typed binding for historical prospective calibration."""

    schema_version: Literal["historical-calibration-policy/v1"] = "historical-calibration-policy/v1"
    admission_id: Hash
    profile_hash: Hash
    dataset_hash: Hash
    code_revision: str = Field(min_length=1, max_length=200)
    training_start_ns: int = Field(ge=0)
    training_end_ns: int = Field(gt=0)
    no_pruning: Literal[True] = True

    @model_validator(mode="after")
    def ordered(self):
        if self.training_start_ns >= self.training_end_ns:
            raise ValueError("empty/reversed calibration coverage window")
        return self


class HistoricalCohortRequest(Contract):
    schema_version: Literal["historical-screen-cohort/v2"] = "historical-screen-cohort/v2"
    policy: HistoricalCalibrationPolicy
    calibration_experiments: tuple[Hash, ...] = Field(min_length=1, max_length=128)
    prospective_job_ids: tuple[Annotated[str, Field(min_length=1, max_length=64)], ...] = Field(
        min_length=1, max_length=256
    )
    audit_sample_count: int = Field(ge=1, le=128, strict=True)
    seed: int = Field(ge=0, strict=True)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[HISTORICAL_ATTESTATION]

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
        return self


def subject(profile, spec, contract, revision):
    return {
        "instrument_hash": fingerprint(profile),
        "operator": spec.signal.operator,
        "timeframe": spec.timeframe,
        "confirmations": list(spec.confirmations),
        "scenario": contract.scenario,
        "code_revision": revision,
        "policy_hash": fingerprint(CostHorizonPolicy()),
    }


class HistoricalCohorts:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def _native_artifact(self, experiment_hash):
        path = self.root / "artifacts" / (experiment_hash + ".json")
        try:
            if path.is_symlink():
                raise ValueError("native artifact symlink")
            return sha256(path)
        except OSError as exc:
            raise ValueError("native artifact unavailable") from exc

    def _diagnostic(self, experiment_hash):
        """Load the retained posthoc diagnostic bound to this native experiment."""
        rows = self.store.rows(
            "SELECT artifact_hash FROM experiments WHERE experiment_hash=?", (experiment_hash,)
        )
        if not rows:
            raise ValueError("calibration requires a retained native experiment")
        native_hash = rows[0]["artifact_hash"]
        events = self.store.rows(
            "SELECT payload FROM audit_events WHERE action='historical_shadow_completed' "
            "AND json_extract(payload,'$.native_artifact_hash')=? ORDER BY created_at",
            (native_hash,),
        )
        if not events:
            raise ValueError("calibration requires a retained historical diagnostic")
        payload = json.loads(events[-1]["payload"])
        path = self.root / "artifacts" / "historical-shadow" / (payload["diagnostic_id"] + ".json")
        try:
            if path.is_symlink() or sha256(path) != payload["artifact_hash"]:
                raise ValueError("diagnostic artifact integrity")
            body = json.loads(path.read_text())
        except OSError as exc:
            raise ValueError("diagnostic artifact unavailable") from exc
        if fingerprint(body) != payload["artifact_hash"]:
            raise ValueError("diagnostic body integrity")
        if body["request"]["experiment_hash"] != experiment_hash:
            raise ValueError("diagnostic experiment binding mismatch")
        return body

    def _spec_for(self, strategy_hash):
        rows = self.store.rows(
            "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (strategy_hash,)
        )
        if not rows:
            raise ValueError("calibration strategy specification unavailable")
        return StrategySpec.model_validate_json(rows[0]["spec_json"])

    def freeze(self, request):
        request = HistoricalCohortRequest.model_validate(request)
        prior = self.store.rows(
            "SELECT cohort_id FROM screen_cohorts WHERE json_extract(body_json,'$.request_hash')=?",
            (fingerprint(request),),
        )
        if prior:
            return prior[0]["cohort_id"]
        revision = execution_revision()
        policy = request.policy
        if policy.code_revision != revision:
            raise ValueError("historical calibration requires the current code revision")
        if policy.no_pruning is not True:
            raise ValueError("historical calibration requires an explicit no-pruning policy")
        catalog = Catalog(self.root / "catalog")
        registry = InputRegistry(self.root, catalog)
        calibration = []
        for experiment in request.calibration_experiments:
            body = self._diagnostic(experiment)
            contract = ExperimentContract.model_validate(body["contract"])
            profile = InstrumentSpec.model_validate(body["request"]["profile"])
            spec = self._spec_for(contract.strategy_hash)
            if profile.synthetic or contract.evaluation_policy == HISTORICAL_TRAINING_POLICY:
                raise ValueError(
                    "historical calibration requires reviewed approved-policy training evidence"
                )
            if admission_identity(contract.evaluation_policy) != policy.admission_id:
                raise ValueError("calibration admission binding mismatch")
            if (
                fingerprint(profile) != policy.profile_hash
                or contract.dataset_hash != policy.dataset_hash
                or contract.code_revision != policy.code_revision
                or body["input_admission"]["admission_id"] != policy.admission_id
                or body["approximate_pruning_authorized"] is not False
            ):
                raise ValueError("calibration policy binding mismatch")
            if len(contract.windows) != 1 or contract.windows[0].role != "train_only":
                raise ValueError("historical calibration is training-only")
            window = contract.windows[0]
            if window.start_ns < policy.training_start_ns or window.end_ns > policy.training_end_ns:
                raise ValueError("calibration training window outside policy coverage")
            if self._native_artifact(experiment) != body["native_artifact_hash"]:
                raise ValueError("calibration native artifact mismatch")
            calibration.append({"diagnostic": body, "contract": contract, "spec": spec})
        comparison = subject(
            InstrumentSpec.model_validate(calibration[0]["diagnostic"]["request"]["profile"]),
            calibration[0]["spec"],
            calibration[0]["contract"],
            revision,
        )
        if any(
            subject(
                InstrumentSpec.model_validate(c["diagnostic"]["request"]["profile"]),
                c["spec"],
                c["contract"],
                revision,
            )
            != comparison
            for c in calibration
        ):
            raise ValueError("calibration subjects differ")
        frame = []
        seen = set(request.calibration_experiments)
        effective = set()
        for identity in request.prospective_job_ids:
            row = self.store.rows("SELECT * FROM jobs WHERE job_id=?", (identity,))
            row = row[0] if row else None
            if (
                row is None
                or row["kind"] != "research"
                or row["state"] not in ("QUEUED", "FAILED_RETRYABLE")
                or row["attempts"]
            ):
                raise ValueError("audit membership must be frozen before any native attempt")
            payload = json.loads(row["payload"])
            contract = ExperimentContract.model_validate(payload["contract"])
            spec = StrategySpec.model_validate(payload["strategy"])
            profile = InstrumentSpec.model_validate(payload["profile"])
            if profile.synthetic or contract.evaluation_policy == HISTORICAL_TRAINING_POLICY:
                raise ValueError("historical cohort requires approved-policy historical evidence")
            if admission_identity(contract.evaluation_policy) != policy.admission_id:
                raise ValueError("prospective admission binding mismatch")
            if (
                (not profile.synthetic and fingerprint(profile) != policy.profile_hash)
                or contract.dataset_hash != policy.dataset_hash
                or contract.code_revision != policy.code_revision
            ):
                raise ValueError("prospective policy binding mismatch")
            if len(contract.windows) != 1 or contract.windows[0].role != "train_only":
                raise ValueError("historical cohort is training-only")
            window = contract.windows[0]
            if window.start_ns < policy.training_end_ns + EMBARGO_NS:
                raise ValueError(
                    "prospective audit requires separate later training with 24h label embargo"
                )
            if subject(profile, spec, contract, revision) != comparison:
                raise ValueError("prospective and calibration subjects differ")
            experiment = contract.experiment_hash
            if (
                experiment in seen
                or self.store.rows(
                    "SELECT 1 FROM experiments WHERE experiment_hash=?", (experiment,)
                )
                or self.store.rows(
                    "SELECT 1 FROM screen_cohort_members WHERE experiment_hash=? AND role='prospective'",
                    (experiment,),
                )
            ):
                raise ValueError("cohort outcome already seen or member already frozen")
            key = fingerprint(
                {k: v for k, v in contract.model_dump(mode="json").items() if k != "seed"}
            )
            if key in effective or self.store.rows(
                "SELECT 1 FROM screen_cohort_effective_inputs WHERE effective_hash=?",
                (key,),
            ):
                raise ValueError("duplicate effective experiment in sampling frame or prior cohort")
            seen.add(experiment)
            effective.add(key)
            manifest = catalog.verify(contract.dataset_hash, deep=True)
            if (
                manifest["instrument"] != profile.instrument
                or manifest["provenance"].get("synthetic") is not False
            ):
                raise ValueError("cohort source/profile mismatch")
            from factory.data.versions import reject_quarantined

            db = self.store.connect()
            try:
                reject_quarantined(db, manifest)
                require_training_scope(db, SimpleNamespace(profile=profile, window=window))
            finally:
                db.close()
            registry.require(contract, profile)
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
                        "policy": fingerprint(policy),
                    }
                ),
            )[: request.audit_sample_count]
        )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "subject": comparison,
            "calibration": [c["diagnostic"] for c in calibration],
            "frame": frame,
            "selected": sorted(selected),
            "scope": (
                "Explicit frozen historical training sampling frame under reviewed admission; "
                "not full-universe independence or strategy validation"
            ),
            "approximate_pruning_authorized": False,
            "historical": True,
        }
        cohort = fingerprint(body)
        if self.store.rows("SELECT 1 FROM screen_cohorts WHERE cohort_id=?", (cohort,)):
            return cohort
        with self.store.transaction() as db:
            db.execute(
                "INSERT INTO screen_cohorts VALUES(?,?,?)", (cohort, serialize(body), time.time())
            )
            db.executemany(
                "INSERT INTO screen_cohort_members VALUES(?,?,?,?,?)",
                [
                    (cohort, c["contract"].experiment_hash, "calibration", None, 0)
                    for c in calibration
                ]
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
                "historical_screen_cohort_frozen",
                {"cohort_id": cohort, "frame": len(frame), "selected": len(selected)},
            )
        return cohort

    def report(self, identity):
        rows = self.store.rows(
            "SELECT body_json FROM screen_cohorts WHERE cohort_id=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown historical screen cohort")
        body = json.loads(rows[0]["body_json"])
        if (
            body.get("schema_version")
            != HistoricalCohortRequest.model_fields["schema_version"].default
        ):
            raise ValueError("not a historical screen cohort")
        if fingerprint(body) != identity:
            raise ValueError("historical screen cohort identity mismatch")
        observations = []
        for experiment in body["selected"]:
            rows = self.store.rows(
                "SELECT artifact_hash FROM experiments WHERE experiment_hash=?", (experiment,)
            )
            if not rows:
                continue
            events = self.store.rows(
                "SELECT payload FROM audit_events WHERE action='historical_shadow_completed' "
                "AND json_extract(payload,'$.native_artifact_hash')=? ORDER BY created_at",
                (rows[0]["artifact_hash"],),
            )
            if not events:
                continue
            payload = json.loads(events[-1]["payload"])
            path = (
                self.root / "artifacts" / "historical-shadow" / (payload["diagnostic_id"] + ".json")
            )
            if path.is_symlink() or sha256(path) != payload["artifact_hash"]:
                raise ValueError("observed diagnostic integrity")
            observations.append(json.loads(path.read_text()))
        rejected = [o for o in observations if o["estimate"].get("rejection_suggested")]
        false = sum(bool(o["observed_false_negative"]) for o in rejected)
        counterexamples = (
            sum(bool(o["observed_false_negative"]) for o in body["calibration"]) + false
        )
        return {
            "cohort_id": identity,
            "schema_version": body["schema_version"],
            "historical": True,
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
                "Reviewed admission is not broker execution or independent strategy qualification",
                "No OOS, holdout, ranking qualification or independent strategy evidence",
                "Native source/code changes require a new cohort; reused identities do not add independent observations",
            ],
        }


def selected_historical_cohort(store, contract):
    rows = store.rows(
        "SELECT m.cohort_id FROM screen_cohort_members m "
        "JOIN screen_cohorts c ON c.cohort_id=m.cohort_id "
        "WHERE m.experiment_hash=? AND m.role='prospective' AND m.selected=1 "
        "AND json_extract(c.body_json,'$.schema_version')='historical-screen-cohort/v2'",
        (contract.experiment_hash,),
    )
    return rows[0]["cohort_id"] if rows else None
