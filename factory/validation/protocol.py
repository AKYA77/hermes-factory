"""Persistent chronological refitting/selection and immutable evaluation stages.

Fold TPE studies consume only that fold's earlier training objectives. OOS is
never an optimizer objective. Annual/pooled views are retrospective native runs,
not sums of independently reset fold equity. Statistical decisions remain labeled.
"""

from decimal import Decimal as D
import json
from pathlib import Path
import time
from typing import Literal

from pydantic import Field, model_validator

from factory.contracts import (
    Contract,
    ExperimentContract,
    StrategySpec,
    Window,
    TIMEFRAMES,
    fingerprint,
    serialize,
)
from factory.data import Catalog, atomic_bytes, sha256
from factory.exploration.persistent import Search, SearchProtocol
from factory.validation import quarter_folds
from factory.validation.access import Holdouts, HoldoutSpec
from factory.validation.statistics import annual_windows, outcome_summary, holm, stability_summary
from factory.simulation.ledger import require_execution_version


class ValidationCriteria(Contract):
    min_oos_closed_trades: int = Field(ge=50, le=10000)
    min_full_folds: int = Field(ge=1, le=8)
    min_annual_closed_trades: int = Field(ge=50, le=10000)
    min_wilson_lower: float = Field(ge=0, le=1, allow_inf_nan=False)
    min_net_profit: D = Field(ge=0)
    max_losing_streak: int = Field(ge=1, le=10000)
    familywise_alpha: float = Field(gt=0, lt=1, allow_inf_nan=False)
    min_neighborhoods_with_trades: int = Field(ge=1, le=10)
    require_research_targets: bool


class ValidationProtocol(Contract):
    schema_version: Literal["scientific-validation/v1"] = "scientific-validation/v1"
    holdout: HoldoutSpec
    start_ns: int = Field(ge=0)
    family: Literal["momentum", "mean_reversion", "breakout"]
    timeframe: str
    confirmations: tuple[str, ...] = ()
    seed: int = Field(ge=0, le=2**32 - 1)
    trials_per_refit: int = Field(ge=1, le=32)
    cpu_seconds_per_refit: float = Field(gt=0, le=3600, allow_inf_nan=False)
    purge_seconds: int = Field(ge=0, le=86400)
    embargo_seconds: int = Field(ge=0, le=86400)
    criteria: ValidationCriteria

    @model_validator(mode="after")
    def coherent(self):
        if not self.holdout.profile.synthetic:
            raise ValueError(
                "REAL_MONETARY_PROFILE_GATE: verified profile/conversion support required"
            )
        if self.timeframe not in TIMEFRAMES or len(self.confirmations) > 1:
            raise ValueError("unsupported protocol timeframes")
        if any(
            tf not in TIMEFRAMES or TIMEFRAMES[tf] <= TIMEFRAMES[self.timeframe]
            for tf in self.confirmations
        ):
            raise ValueError("invalid higher confirmation")
        if self.start_ns >= self.holdout.window.start_ns:
            raise ValueError("development must precede final holdout")
        if not self.folds():
            raise ValueError("at least one chronological quarter fold required")
        return self

    @property
    def protocol_id(self):
        raw = self.model_dump()
        raw["cpu_seconds_per_refit"] = float(self.cpu_seconds_per_refit)
        # Models validate all explicit float criteria at construction.
        return fingerprint(raw)

    def folds(self):
        folds = []
        for fold in quarter_folds(self.start_ns, self.holdout.window.start_ns):
            train_end = fold["train_end"] - self.purge_seconds * 10**9
            oos_start = fold["oos_start"] + self.embargo_seconds * 10**9
            if train_end <= self.start_ns or oos_start >= fold["oos_end"]:
                raise ValueError("purge/embargo leaves empty fold")
            folds.append({**fold, "train_end": train_end, "oos_start": oos_start})
        return folds


class ValidationController:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def register(self, protocol):
        m = Catalog(self.root / "catalog").verify(protocol.holdout.dataset_hash, deep=True)
        if protocol.start_ns < m["first_ns"]:
            raise ValueError("validation start precedes source")
        identity = protocol.protocol_id
        holdout_id = Holdouts(self.root).register(protocol.holdout)
        with self.store.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO validation_protocols VALUES(?,?,?,?)",
                (identity, serialize(protocol), holdout_id, time.time()),
            )
            db.execute("INSERT OR IGNORE INTO validation_controls VALUES(?,1,0)", (identity,))
            self.store._audit(
                db, "validation", "scientific_protocol_registered", {"protocol_id": identity}
            )
        return identity

    def protocol(self, identity):
        rows = self.store.rows(
            "SELECT spec_json FROM validation_protocols WHERE protocol_id=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown scientific validation protocol")
        p = ValidationProtocol.model_validate_json(rows[0]["spec_json"])
        if p.protocol_id != identity:
            raise ValueError("validation protocol identity mismatch")
        return p

    def refit(self, p, index, end_ns):
        rows = self.store.rows(
            "SELECT search_protocol_hash FROM validation_training_regions WHERE protocol_id=? AND fold_index=?",
            (p.protocol_id, index),
        )
        if not rows:
            search_protocol = SearchProtocol(
                dataset_hash=p.holdout.dataset_hash,
                profile=p.holdout.profile,
                window=Window(start_ns=p.start_ns, end_ns=end_ns, role="train_only"),
                family=p.family,
                timeframe=p.timeframe,
                confirmation_options=p.confirmations or ("none",),
                code_revision=p.holdout.code_revision,
                seed=(p.seed + index + 1) % (2**32),
                max_trials=p.trials_per_refit,
                cpu_budget_seconds=p.cpu_seconds_per_refit,
            )
            search_hash = Search(self.store, self.root).register(search_protocol)
            with self.store.transaction() as db:
                db.execute(
                    "INSERT OR IGNORE INTO validation_training_regions VALUES(?,?,?,?)",
                    (p.protocol_id, index, search_hash, time.time()),
                )
            return None
        search_hash = rows[0]["search_protocol_hash"]
        history = self.store.rows(
            """SELECT t.*,o.outcome,o.run_id FROM search_trials t
            LEFT JOIN search_outcomes o USING(trial_id) WHERE protocol_hash=? ORDER BY trial_number""",
            (search_hash,),
        )
        if any(row["outcome"] is None for row in history):
            return None
        # Budget exhaustion is an explicit bounded end condition, not success.
        search_protocol = Search(self.store, self.root).protocol(search_hash)
        probe = search_protocol.strategy(
            {"lookback": 2, "threshold_tenths": 5, "stop_ticks": 20, "confirmation": "none"}
        )
        require_execution_version(search_protocol.contract(probe))
        used = self.store.rows(
            """SELECT coalesce(sum(t.generation_cpu_seconds+coalesce(o.cpu_seconds,0)),0) cpu
            FROM search_trials t LEFT JOIN search_outcomes o USING(trial_id) WHERE protocol_hash=?""",
            (search_hash,),
        )[0]["cpu"]
        if len(history) < p.trials_per_refit and used < search_protocol.cpu_budget_seconds:
            return None
        candidates = []
        for row in history:
            if row["run_id"]:
                experiment = self.store.rows(
                    "SELECT * FROM experiments WHERE run_id=?", (row["run_id"],)
                )[0]
                result = self.verified(experiment)
                candidates.append(
                    (
                        D(result["ending_equity"]),
                        experiment["strategy_id"],
                        row["run_id"],
                        experiment,
                    )
                )
        if not candidates:
            raise ValueError("NO_VERIFIED_TRAINING_CANDIDATE")
        # Fixed training-only tie rule; never inspect fold OOS to choose a model.
        return sorted(candidates, key=lambda item: (-item[0], item[1], item[2]))[0][3]

    def verified(self, experiment):
        result = json.loads(experiment["result_json"])
        artifact = self.root / "artifacts" / (experiment["experiment_hash"] + ".json")
        contract = ExperimentContract.model_validate_json(experiment["contract_json"])
        require_execution_version(contract)
        if (
            fingerprint(result) != experiment["artifact_hash"]
            or sha256(artifact) != experiment["artifact_hash"]
            or json.loads(artifact.read_bytes()) != result
            or result.get("integrity_errors")
            or not result.get("synthetic")
            or any(w.role != "train_only" for w in contract.windows)
        ):
            raise ValueError("validation training artifact mismatch")
        return result

    def stage(
        self, p, name, training, window, *, strategy=None, retrospective=False, scenario=None
    ):
        original = ExperimentContract.model_validate_json(training["contract_json"])
        self.verified(training)
        raw = self.store.rows(
            "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (training["strategy_id"],)
        )[0]["spec_json"]
        spec = strategy or StrategySpec.model_validate_json(raw)
        self.store.register_strategy(
            spec,
            parent=training["strategy_id"]
            if spec.strategy_hash != training["strategy_id"]
            else None,
            hypothesis="predeclared training parameter neighborhood" if strategy else None,
        )
        contract = ExperimentContract.model_validate(
            {
                **original.model_dump(),
                "strategy_hash": spec.strategy_hash,
                "windows": (window,),
                "scenario": scenario or original.scenario,
                "evaluation_policy": "scientific-validation/v1:" + p.protocol_id + ":" + name,
            }
        )
        identity = fingerprint(
            {"protocol": p.protocol_id, "name": name, "contract": contract.experiment_hash}
        )
        payload = {
            "contract": contract.model_dump(mode="json"),
            "strategy": spec.model_dump(mode="json"),
            "profile": p.holdout.profile.model_dump(mode="json"),
            "validation_stage_id": identity,
        }
        if retrospective:
            payload["report_authorization"] = fingerprint(
                {"stage": identity, "purpose": "retrospective-report/v1"}
            )
        with self.store.transaction() as db:
            existing = db.execute(
                "SELECT payload_json FROM validation_stages WHERE stage_id=?", (identity,)
            ).fetchone()
            if existing and existing[0] != serialize(payload):
                raise ValueError("immutable validation stage conflict")
            db.execute(
                "INSERT OR IGNORE INTO validation_stages VALUES(?,?,?,?,?,?)",
                (
                    identity,
                    p.protocol_id,
                    name,
                    serialize(payload),
                    training["run_id"],
                    time.time(),
                ),
            )
            if retrospective:
                holdout_id = p.holdout.holdout_id
                consumed = db.execute(
                    "SELECT 1 FROM holdout_consumptions WHERE holdout_id=?", (holdout_id,)
                ).fetchone()
                if not consumed or window.role != "report_only" or strategy is not None:
                    raise ValueError("report authorization requires consumed frozen parent")
                selected = db.execute(
                    "SELECT training_run_id FROM holdout_selections WHERE holdout_id=?",
                    (holdout_id,),
                ).fetchone()
                if selected[0] != training["run_id"]:
                    raise ValueError("report must use the frozen holdout candidate")
                db.execute(
                    "INSERT OR IGNORE INTO retrospective_report_authorizations VALUES(?,?,?,?,?)",
                    (
                        payload["report_authorization"],
                        holdout_id,
                        serialize(contract),
                        identity,
                        time.time(),
                    ),
                )
        self.store.enqueue(
            "validation",
            payload,
            contract.experiment_hash,
            actor="scientific-validation",
            priority=40,
        )
        rows = self.store.rows(
            "SELECT * FROM evaluation_results WHERE evaluation_id=?", (contract.experiment_hash,)
        )
        if not rows:
            jobs = self.store.rows(
                "SELECT state,error FROM jobs WHERE idempotency_key=?", (contract.experiment_hash,)
            )
            if jobs and jobs[0]["state"] in ("FAILED_FINAL", "CANCELLED"):
                raise ValueError("EVALUATION_STAGE_FAILED: " + str(jobs[0]["error"]))
            return None
        row = rows[0]
        result = json.loads(row["result_json"])
        artifact = self.root / "artifacts" / "evaluations" / (contract.experiment_hash + ".json")
        if (
            row["contract_json"] != serialize(contract)
            or fingerprint(result) != row["artifact_hash"]
            or sha256(artifact) != row["artifact_hash"]
        ):
            raise ValueError("evaluation stage artifact mismatch")
        return {
            "evaluation_id": contract.experiment_hash,
            "artifact_hash": row["artifact_hash"],
            "result": result,
        }

    def advance(self):
        if self.store.paused():
            return False
        active = self.store.rows(
            "SELECT count(*) n FROM jobs WHERE state IN ('QUEUED','RUNNING','FAILED_RETRYABLE')"
        )[0]["n"]
        if active >= 2:
            return False
        protocols = self.store.rows("""SELECT p.* FROM validation_protocols p JOIN validation_controls c USING(protocol_id)
            LEFT JOIN validation_protocol_reports r USING(protocol_id) WHERE c.enabled=1 AND r.protocol_id IS NULL
            ORDER BY c.last_tick,p.created_at,p.protocol_id LIMIT 32""")
        for row in protocols:
            p = self.protocol(row["protocol_id"])
            with self.store.transaction() as db:
                db.execute(
                    "UPDATE validation_controls SET last_tick=? WHERE protocol_id=?",
                    (time.time(), p.protocol_id),
                )
            try:
                return self._advance(p)
            except (ValueError, OSError) as exc:
                self.finish(
                    p,
                    {
                        "status": "FAILED_CHECKS",
                        "reason": str(exc),
                        "independently_validated": False,
                    },
                )
                return True
        return False

    def _advance(self, p):
        folds = []
        for index, fold in enumerate(p.folds()):
            selected = self.refit(p, index, fold["train_end"])
            if selected is None:
                return True
            completed = self.stage(
                p,
                "fold-" + str(index),
                selected,
                Window(start_ns=fold["oos_start"], end_ns=fold["oos_end"], role="selection_oos"),
            )
            if completed is None:
                return True
            folds.append({"fold": fold, "training_run_id": selected["run_id"], **completed})
        training_end = p.holdout.window.start_ns - p.purge_seconds * 10**9
        final = self.refit(p, -1, training_end)
        if final is None:
            return True
        base_result = self.verified(final)
        base = outcome_summary(base_result["trades"])
        neighborhoods = []
        for index, child in enumerate(
            neighbors(
                StrategySpec.model_validate_json(
                    self.store.rows(
                        "SELECT spec_json FROM strategy_specs WHERE strategy_id=?",
                        (final["strategy_id"],),
                    )[0]["spec_json"]
                )
            )
        ):
            completed = self.stage(
                p,
                "neighbor-" + str(index),
                final,
                Window(start_ns=p.start_ns, end_ns=training_end, role="train_only"),
                strategy=child,
            )
            if completed is None:
                return True
            parent_spec = StrategySpec.model_validate_json(
                self.store.rows(
                    "SELECT spec_json FROM strategy_specs WHERE strategy_id=?",
                    (final["strategy_id"],),
                )[0]["spec_json"]
            )
            neighborhoods.append(
                {
                    **completed,
                    "strategy": child.model_dump(mode="json"),
                    "changed_fields": [
                        key
                        for key, value in child.model_dump().items()
                        if parent_spec.model_dump()[key] != value
                    ],
                    "purpose": "predeclared training sensitivity, never holdout selection",
                }
            )
        # No neighborhood is selected using OOS or final holdout; it is sensitivity evidence.
        holdouts = Holdouts(self.root)
        holdouts.freeze(p.holdout.holdout_id, final["run_id"])
        queued = holdouts.enqueue(p.holdout.holdout_id)
        held = self.store.rows(
            "SELECT * FROM evaluation_results WHERE evaluation_id=?", (queued["evaluation_id"],)
        )
        if not held:
            jobs = self.store.rows(
                "SELECT state,error FROM jobs WHERE job_id=?", (queued["job_id"],)
            )
            if jobs[0]["state"] in ("FAILED_FINAL", "CANCELLED"):
                raise ValueError("FINAL_CONFIRMATION_FAILED: " + str(jobs[0]["error"]))
            return True
        holdout_result = json.loads(held[0]["result_json"])
        if (
            fingerprint(holdout_result) != held[0]["artifact_hash"]
            or sha256(self.root / "artifacts" / "evaluations" / (queued["evaluation_id"] + ".json"))
            != held[0]["artifact_hash"]
        ):
            raise ValueError("holdout result integrity mismatch")
        annual = []
        for year in annual_windows(p.start_ns, p.holdout.window.end_ns):
            completed = self.stage(
                p,
                "annual-" + str(year["year"]),
                final,
                Window(start_ns=year["start_ns"], end_ns=year["end_ns"], role="report_only"),
                retrospective=True,
            )
            if completed is None:
                return True
            annual.append({"year": year, **completed})
        pooled = self.stage(
            p,
            "pooled-retrospective",
            final,
            Window(start_ns=p.start_ns, end_ns=p.holdout.window.end_ns, role="report_only"),
            retrospective=True,
        )
        if pooled is None:
            return True
        reference = self.stage(
            p,
            "cost-reference-training",
            final,
            Window(start_ns=p.start_ns, end_ns=training_end, role="train_only"),
            scenario="historical-reference/v1",
        )
        if reference is None:
            return True
        summaries = [
            outcome_summary(item["result"]["windows"][0]["replay"]["trades"])
            if item["result"]["windows"][0].get("replay")
            else outcome_summary([])
            for item in folds
        ]
        held_summary = (
            outcome_summary(holdout_result["windows"][0]["replay"]["trades"])
            if holdout_result["windows"][0].get("replay")
            else outcome_summary([])
        )
        neighborhood_summaries = [
            outcome_summary(item["result"]["windows"][0]["replay"]["trades"])
            if item["result"]["windows"][0].get("replay")
            else outcome_summary([])
            for item in neighborhoods
        ]
        decision = decide(p, folds, summaries, held_summary, annual, neighborhood_summaries)
        self.finish(
            p,
            {
                "status": decision["status"],
                "decision": decision,
                "folds": folds,
                "final_training_run_id": final["run_id"],
                "training_metrics": base,
                "holdout": {
                    "evaluation_id": queued["evaluation_id"],
                    "artifact_hash": held[0]["artifact_hash"],
                    "metrics": held_summary,
                },
                "annual": annual,
                "pooled_retrospective": pooled,
                "cost_reference_training": reference,
                "neighborhood": stability_summary(base, neighborhood_summaries),
                "neighborhood_evaluations": neighborhoods,
                "synthetic": True,
                "eligible_for_historical_validated_board": False,
                "independently_validated": decision["status"] == "VALIDATED_REFERENCE",
                "scope": "controlled synthetic software evidence; never a verified historical strategy",
                "counter_semantics": "folds each reset $20; pooled/annual are separate native scenarios, not spliced fold equity",
            },
        )
        return True

    def finish(self, p, report):
        value = {"protocol_id": p.protocol_id, "protocol": p.model_dump(mode="json"), **report}
        digest = fingerprint(value)
        path = self.root / "artifacts" / "validation-protocols" / (p.protocol_id + ".json")
        encoded = serialize(value).encode()
        if path.exists() and path.read_bytes() != encoded:
            raise ValueError("immutable scientific report conflict")
        atomic_bytes(path, encoded)
        with self.store.transaction() as db:
            db.execute(
                "INSERT INTO validation_protocol_reports VALUES(?,?,?,?)",
                (p.protocol_id, serialize(value), digest, time.time()),
            )
            self.store._audit(
                db,
                "validation",
                "scientific_protocol_completed",
                {"protocol_id": p.protocol_id, "status": value["status"]},
            )


def neighbors(parent):
    proposals = []
    for ticks in sorted(
        {max(1, parent.stop_ticks * 9 // 10), min(1000000, (parent.stop_ticks * 11 + 9) // 10)}
    ):
        proposals.append({"stop_ticks": ticks})
    for lookback in sorted(
        {max(2, parent.signal.lookback - 1), min(500, parent.signal.lookback + 1)}
    ):
        proposals.append({"signal": {**parent.signal.model_dump(), "lookback": lookback}})
    for threshold in sorted(
        {
            max(D(".01"), parent.signal.threshold - D(".1")),
            min(D(20), parent.signal.threshold + D(".1")),
        }
    ):
        proposals.append({"signal": {**parent.signal.model_dump(), "threshold": threshold}})
    frames = list(TIMEFRAMES)
    index = frames.index(parent.timeframe)
    for neighbor_index in (index - 1, index + 1):
        if 0 <= neighbor_index < len(frames):
            timeframe = frames[neighbor_index]
            if all(TIMEFRAMES[tf] > TIMEFRAMES[timeframe] for tf in parent.confirmations):
                proposals.append({"timeframe": timeframe})
    if parent.confirmations:
        proposals.append({"confirmations": parent.confirmations[:-1]})
    elif index + 1 < len(frames):
        proposals.append({"confirmations": (frames[index + 1],)})
    seen = {parent.strategy_hash}
    for proposal in proposals:
        candidate = StrategySpec.model_validate({**parent.model_dump(), **proposal})
        if candidate.strategy_hash not in seen:
            seen.add(candidate.strategy_hash)
            yield candidate


def decide(p, folds, summaries, held, annual, neighborhoods):
    c = p.criteria
    tested = summaries + [held]
    missing = any(not f["result"]["windows"][0].get("replay") for f in folds)
    enough = (
        len([f for f in folds if not f["fold"]["partial"]]) >= c.min_full_folds
        and all(s["completed_trades"] >= c.min_oos_closed_trades for s in tested)
        and all(
            (a["result"]["windows"][0].get("metrics") or {}).get("completed_trades", 0)
            >= c.min_annual_closed_trades
            for a in annual
        )
        and sum(bool(n["completed_trades"]) for n in neighborhoods)
        >= c.min_neighborhoods_with_trades
    )
    p_values = [
        s["one_sided_win_fraction_pvalue"]
        if s["one_sided_win_fraction_pvalue"] is not None
        else 1.0
        for s in tested
    ]
    adjusted = holm(p_values, c.familywise_alpha)
    failed = [
        i
        for i, s in enumerate(tested)
        if (
            D(s["ending_balance"]) - 20 < c.min_net_profit
            or s["max_losing_streak"] > c.max_losing_streak
        )
    ]
    confidence = all(s["wilson_95"] and s["wilson_95"][0] >= c.min_wilson_lower for s in tested)
    research_targets = all(
        s["win_rate"] is not None
        and s["win_rate"] >= 0.7
        and D(s["ending_balance"]) >= 500
        and s["max_losing_streak"] <= 5
        for s in tested
    )
    status = (
        "DATA_UNAVAILABLE"
        if missing
        else "INSUFFICIENT_EVIDENCE"
        if not enough
        else "OOS_FAILED"
        if failed
        or not confidence
        or not all(adjusted)
        or (c.require_research_targets and not research_targets)
        else "VALIDATED_REFERENCE"
    )
    return {
        "status": status,
        "sufficient_samples": enough,
        "failed_oos_indices": failed,
        "wilson_gate_passed": confidence,
        "holm_rejections": adjusted,
        "p_values": p_values,
        "research_targets_met": research_targets,
        "multiple_testing_scope": "declared fold + final confirmations; all training trials separately counted; no claim of correction for all researcher discretion",
        "selection_bias_warning": "training candidate search and correlated trades require review; synthetic reference validation is not market validation",
    }
