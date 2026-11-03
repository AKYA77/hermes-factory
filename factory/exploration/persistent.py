"""Serialized, reproducible TPE ask/tell reconstructed from durable trial history.

Optuna never writes its own SQLite store. Factory's coordinated registry is the
persistent source of truth; each bounded ask rebuilds the study from observations
and a trial-specific seed, so restarting does not lose the sampler's evidence.
Only verified, authorized training artifacts supply objective feedback.
"""

import json
import math
from pathlib import Path
import time
from typing import Literal

import optuna
from pydantic import Field, model_validator

from factory.contracts import (
    Contract,
    ExperimentContract,
    InstrumentSpec,
    Signal,
    StrategySpec,
    TIMEFRAMES,
    Window,
    fingerprint,
    serialize,
)
from factory.data import Catalog, sha256
from factory.simulation.ledger import EXECUTION_VERSION, require_execution_version


class SearchProtocol(Contract):
    schema_version: Literal["search/v1"] = "search/v1"
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: InstrumentSpec
    window: Window
    family: Literal["mean_reversion", "momentum", "breakout"]
    timeframe: str
    confirmation_options: tuple[str, ...] = ("none",)
    code_revision: str
    seed: int = Field(ge=0, le=2**32 - 1)
    max_trials: int = Field(default=64, ge=1, le=256)
    cpu_budget_seconds: float = Field(default=600, gt=0, le=86400, allow_inf_nan=False)
    scenario: Literal["historical-reference/v1", "historical-pessimistic/v1"] = (
        "historical-pessimistic/v1"
    )
    objective: Literal["training-net-return/v1"] = "training-net-return/v1"
    optimizer: Literal["optuna-tpe/4.5.0-reseed/v1"] = "optuna-tpe/4.5.0-reseed/v1"
    research_kind: Literal["synthetic-training/v1"] = "synthetic-training/v1"

    @model_validator(mode="after")
    def training_only(self):
        if self.window.role != "train_only":
            raise ValueError("optimizer may use authorized training only, never OOS/holdout")
        if self.timeframe not in TIMEFRAMES or not self.confirmation_options:
            raise ValueError("invalid search timeframes")
        if len(set(self.confirmation_options)) != len(self.confirmation_options):
            raise ValueError("duplicate confirmation choice")
        for tf in self.confirmation_options:
            if tf != "none" and (
                tf not in TIMEFRAMES or TIMEFRAMES[tf] <= TIMEFRAMES[self.timeframe]
            ):
                raise ValueError("confirmation must be higher than entry timeframe")
        if not self.profile.synthetic or self.profile.quote_currency != "USD":
            raise ValueError("real monetary/cross-currency research approval remains blocked")
        return self

    @property
    def protocol_hash(self):
        return fingerprint(self)

    def contract(self, spec):
        return ExperimentContract(
            strategy_hash=spec.strategy_hash,
            dataset_hash=self.dataset_hash,
            instrument_hash=fingerprint(self.profile),
            engine_version="1.231.0",
            code_revision=self.code_revision,
            fill_version=EXECUTION_VERSION,
            evaluation_policy=self.research_kind,
            scenario=self.scenario,
            windows=(self.window,),
            seed=self.seed,
        )

    def distributions(self):
        return {
            "lookback": optuna.distributions.IntDistribution(2, 48),
            "threshold_tenths": optuna.distributions.IntDistribution(5, 30),
            "stop_ticks": optuna.distributions.IntDistribution(20, 200, step=10),
            "confirmation": optuna.distributions.CategoricalDistribution(self.confirmation_options),
        }

    def strategy(self, params):
        from decimal import Decimal

        return StrategySpec(
            instrument=self.profile.instrument,
            timeframe=self.timeframe,
            signal=Signal(
                operator=self.family,
                lookback=params["lookback"],
                threshold=Decimal(params["threshold_tenths"]) / 10,
            ),
            confirmations=() if params["confirmation"] == "none" else (params["confirmation"],),
            stop_ticks=params["stop_ticks"],
        )


def rebuild_study(protocol, history, number):
    """Deterministic for ordered history; no ephemeral RNG state must survive."""
    from importlib.metadata import version

    if version("optuna") != "4.5.0":
        raise ValueError("unsupported optimizer runtime version")
    seed = int(fingerprint({"seed": protocol.seed, "trial": number})[:8], 16)
    study = optuna.create_study(
        direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed, n_startup_trials=8)
    )
    for row in history:
        state = (
            optuna.trial.TrialState[row["outcome"]]
            if row.get("outcome")
            else optuna.trial.TrialState.RUNNING
        )
        study.add_trial(
            optuna.trial.create_trial(
                state=state,
                value=row.get("objective"),
                params=json.loads(row["parameters_json"]),
                distributions=protocol.distributions(),
            )
        )
    return study


class Search:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def register(self, protocol):
        # Fail closed on real-data or obsolete-source prerequisites.
        probe = protocol.strategy(
            {"lookback": 2, "threshold_tenths": 5, "stop_ticks": 20, "confirmation": "none"}
        )
        require_execution_version(protocol.contract(probe))
        m = Catalog(self.root / "catalog").verify(protocol.dataset_hash)
        if not m["provenance"].get("synthetic") or m["instrument"] != protocol.profile.instrument:
            raise ValueError("source/profile research identity not approved")
        if (
            protocol.window.start_ns < m["first_ns"]
            or protocol.window.end_ns > m["latest_verified_ns"] + 1
        ):
            raise ValueError("training window exceeds verified source bounds")
        with self.store.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO search_protocols VALUES(?,?,?)",
                (protocol.protocol_hash, serialize(protocol), time.time()),
            )
            db.execute(
                "INSERT OR IGNORE INTO search_controls VALUES(?,1,NULL,?)",
                (protocol.protocol_hash, time.time()),
            )
            self.store._audit(
                db, "research", "register_protocol", {"protocol_hash": protocol.protocol_hash}
            )
        return protocol.protocol_hash

    def protocol(self, identity):
        rows = self.store.rows(
            "SELECT protocol_json FROM search_protocols WHERE protocol_hash=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown search protocol")
        return SearchProtocol.model_validate_json(rows[0]["protocol_json"])

    def ask(self, identity):
        protocol = self.protocol(identity)
        require_execution_version(
            protocol.contract(
                protocol.strategy(
                    {"lookback": 2, "threshold_tenths": 5, "stop_ticks": 20, "confirmation": "none"}
                )
            )
        )
        started = time.process_time()
        with self.store.transaction() as db:
            enabled = db.execute(
                "SELECT enabled FROM search_controls WHERE protocol_hash=?", (identity,)
            ).fetchone()
            if not enabled or not enabled[0]:
                return None
            history = [
                dict(r)
                for r in db.execute(
                    """SELECT t.*,o.outcome,o.objective,o.cpu_seconds
                  FROM search_trials t LEFT JOIN search_outcomes o USING(trial_id)
                  WHERE t.protocol_hash=? ORDER BY trial_number""",
                    (identity,),
                )
            ]
            used = sum(r["generation_cpu_seconds"] + (r["cpu_seconds"] or 0) for r in history)
            if len(history) >= protocol.max_trials or used >= protocol.cpu_budget_seconds:
                return None
            number = len(history)
            study = rebuild_study(protocol, history, number)
            trial = study.ask(fixed_distributions=protocol.distributions())
            params = trial.params
            spec = protocol.strategy(params)
            contract = protocol.contract(spec)
            trial_id = fingerprint({"protocol": identity, "trial_number": number})
            db.execute(
                "INSERT INTO search_trials VALUES(?,?,?,?,?,?,?,?)",
                (
                    trial_id,
                    identity,
                    number,
                    serialize(params),
                    serialize(spec),
                    serialize(contract),
                    time.process_time() - started,
                    time.time(),
                ),
            )
            db.execute(
                "UPDATE research_coverage SET proposals=proposals+1,cpu_seconds=cpu_seconds+? "
                "WHERE instrument=? AND family=? AND timeframe=?",
                (
                    time.process_time() - started,
                    protocol.profile.instrument,
                    protocol.family,
                    protocol.timeframe,
                ),
            )
            duplicate = any(
                json.loads(row["contract_json"])["strategy_hash"] == spec.strategy_hash
                for row in history
            )
            if duplicate:
                db.execute(
                    "INSERT INTO search_outcomes VALUES(?,'PRUNED',NULL,NULL,0,?,?)",
                    (trial_id, "EXACT_DUPLICATE_SPEC", time.time()),
                )
            self.store._audit(
                db, "research", "trial_proposed", {"trial_id": trial_id, "duplicate": duplicate}
            )
            return {
                "trial_id": trial_id,
                "spec": spec,
                "contract": contract,
                "duplicate": duplicate,
            }

    def pending(self):
        return self.store.rows("""SELECT t.* FROM search_trials t
             LEFT JOIN search_outcomes o USING(trial_id) WHERE o.trial_id IS NULL
             ORDER BY t.created_at,t.trial_id""")

    def set_enabled(self, identity, enabled, actor="operator"):
        protocol = self.protocol(identity)
        if enabled:
            probe = protocol.strategy(
                {"lookback": 2, "threshold_tenths": 5, "stop_ticks": 20, "confirmation": "none"}
            )
            require_execution_version(protocol.contract(probe))
        with self.store.transaction() as db:
            db.execute(
                "UPDATE search_controls SET enabled=?,reason=?,updated_at=? WHERE protocol_hash=?",
                (int(enabled), None if enabled else "OPERATOR_DISABLED", time.time(), identity),
            )
            self.store._audit(
                db,
                actor,
                "research_enable" if enabled else "research_disable",
                {"protocol_hash": identity},
            )

    def ready_to_enqueue(self, row):
        control = self.store.rows(
            "SELECT * FROM search_controls WHERE protocol_hash=?", (row["protocol_hash"],)
        )[0]
        contract = ExperimentContract.model_validate_json(row["contract_json"])
        reason = None
        if not control["enabled"]:
            reason = control["reason"] or "PROTOCOL_DISABLED"
        else:
            try:
                require_execution_version(contract)
            except ValueError:
                reason = "STALE_SOURCE"
        if reason:
            with self.store.transaction() as db:
                db.execute(
                    "INSERT OR IGNORE INTO search_outcomes VALUES(?,'FAIL',NULL,NULL,0,?,?)",
                    (row["trial_id"], reason, time.time()),
                )
                self.store._audit(
                    db,
                    "research",
                    "pending_trial_blocked",
                    {"trial_id": row["trial_id"], "reason": reason},
                )
            return False
        return True

    def enqueue_pending(self):
        # Idempotent recovery if a coordinator died after durable ask, before enqueue.
        count = 0
        for row in self.pending():
            if not self.ready_to_enqueue(row):
                continue
            protocol = self.protocol(row["protocol_hash"])
            contract = ExperimentContract.model_validate_json(row["contract_json"])
            payload = {
                "strategy": json.loads(row["spec_json"]),
                "contract": json.loads(row["contract_json"]),
                "profile": protocol.profile.model_dump(mode="json"),
            }
            self.store.enqueue("research", payload, contract.experiment_hash, actor="research")
            count += 1
        return count

    def feedback(self):
        applied = 0
        for row in self.pending():
            contract = ExperimentContract.model_validate_json(row["contract_json"])
            protocol = self.protocol(row["protocol_hash"])
            if (
                any(w.role != "train_only" for w in contract.windows)
                or contract.evaluation_policy != protocol.research_kind
            ):
                raise ValueError("optimizer observation leakage")
            jobs = self.store.rows(
                "SELECT * FROM jobs WHERE idempotency_key=?", (contract.experiment_hash,)
            )
            experiments = self.store.rows(
                "SELECT * FROM experiments WHERE experiment_hash=?", (contract.experiment_hash,)
            )
            if jobs and jobs[0]["state"] not in ("COMPLETED", "FAILED_FINAL", "CANCELLED"):
                continue
            if not experiments and not jobs:
                continue
            outcome, objective, run_id, reason = "FAIL", None, None, "WORKER_FAILED"
            cpu = 0.0
            if jobs:
                if jobs[0]["created_at"] >= row["created_at"]:
                    attempts = self.store.rows(
                        "SELECT r.resources_json FROM attempt_resources r JOIN attempts a USING(token) WHERE a.job_id=?",
                        (jobs[0]["job_id"],),
                    )
                    cpu = sum(
                        float(json.loads(a["resources_json"])["cpu_seconds"]) for a in attempts
                    )
                else:
                    cpu = 0.0  # An existing exact run was reused, not executed again.
            if experiments:
                experiment = experiments[0]
                if (
                    experiment["contract_json"] != serialize(contract)
                    or experiment["status"] == "FAILED_CHECKS"
                ):
                    raise ValueError("unverified optimizer observation")
                result = json.loads(experiment["result_json"])
                path = self.root / "artifacts" / f"{contract.experiment_hash}.json"
                try:
                    valid = (
                        sha256(path) == experiment["artifact_hash"]
                        and json.loads(path.read_text()) == result
                        and fingerprint(result) == experiment["artifact_hash"]
                    )
                except (OSError, ValueError) as exc:
                    raise ValueError("optimizer artifact integrity mismatch") from exc
                if not valid:
                    raise ValueError("optimizer artifact integrity mismatch")
                if result.get("integrity_errors") or not result.get("synthetic"):
                    raise ValueError("optimizer observation failed source/execution gates")
                run_id = experiment["run_id"]
                if result["trades"]:
                    from decimal import Decimal as D

                    objective = float((D(result["ending_equity"]) - 20) / 20)
                    outcome, reason = "COMPLETE", "AUTHORIZED_TRAINING_ONLY"
                else:
                    outcome, reason = "PRUNED", "NO_CLOSED_TRADES_IN_TRAINING"
            elif jobs and jobs[0]["state"] == "CANCELLED":
                reason = "CANCELLED"
            elif jobs:
                reason = jobs[0]["error"] or reason
            if (
                not math.isfinite(cpu)
                or cpu < 0
                or (objective is not None and not math.isfinite(objective))
            ):
                raise ValueError("nonfinite optimizer observation")
            with self.store.transaction() as db:
                inserted = db.execute(
                    "INSERT OR IGNORE INTO search_outcomes VALUES(?,?,?,?,?,?,?)",
                    (row["trial_id"], outcome, objective, run_id, cpu, reason, time.time()),
                )
                if inserted.rowcount:
                    db.execute(
                        "UPDATE research_coverage SET cpu_seconds=cpu_seconds+? WHERE instrument=? AND family=? AND timeframe=?",
                        (cpu, protocol.profile.instrument, protocol.family, protocol.timeframe),
                    )
                self.store._audit(
                    db,
                    "research",
                    "training_feedback",
                    {"trial_id": row["trial_id"], "run_id": run_id, "outcome": outcome},
                )
            applied += 1
        return applied


def status(store):
    """Separate trials, duplicates, referenced runs, failures and measured CPU."""
    counts = store.rows("SELECT outcome,count(*) count FROM search_outcomes GROUP BY outcome")
    cpu = store.rows("SELECT coalesce(sum(cpu_seconds),0) cpu FROM search_outcomes")[0]["cpu"]
    generation = store.rows(
        "SELECT coalesce(sum(generation_cpu_seconds),0) cpu FROM search_trials"
    )[0]["cpu"]
    return {
        "scope": "synthetic authorized training only; no independent validation",
        "paused": store.paused(),
        "protocols": store.rows("SELECT count(*) count FROM search_controls WHERE enabled=1")[0][
            "count"
        ],
        "trials_considered": store.rows("SELECT count(*) count FROM search_trials")[0]["count"],
        "exact_duplicates_skipped": store.rows(
            "SELECT count(*) count FROM search_outcomes WHERE reason='EXACT_DUPLICATE_SPEC'"
        )[0]["count"],
        "outcomes": counts,
        "distinct_referenced_simulations": store.rows(
            "SELECT count(DISTINCT run_id) count FROM search_outcomes WHERE run_id IS NOT NULL"
        )[0]["count"],
        "measured_replay_cpu_seconds": cpu,
        "measured_generation_cpu_seconds": generation,
        "independent_validations": 0,
        "limitations": [
            "not a multi-day soak",
            "budgets checked between jobs; one job may overshoot a soft CPU budget",
            "explicit registered regions only; no approved real monetary profiles",
            "all families, automated improvement/selection and screen-rejection audits unfinished",
        ],
    }
