"""Durable diagnosis-driven, budgeted training improvement of registered regions.

Only actual verified training runs can become parents. Independent evaluation is
never read or optimized here. This bounded round preserves all negative evidence;
it does not confer validation or recursively expand descendants without limits.
"""

from collections import Counter
from decimal import Decimal as D
import json
from pathlib import Path
import time
from typing import Literal

from pydantic import Field

from factory.contracts import Contract, ExperimentContract, StrategySpec, fingerprint, serialize
from factory.data import sha256
from factory.exploration.persistent import Search
from factory.improvement import children
from factory.reporting import metrics
from factory.screening import SCREEN_POLICY, verify_pruned
from factory.simulation.ledger import require_execution_version


class ImprovementPolicy(Contract):
    schema_version: Literal["improvement/v1"] = "improvement/v1"
    search_protocol_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    max_parent_plans: int = Field(default=8, ge=1, le=32)
    max_children: int = Field(default=4, ge=1, le=4)
    cpu_budget_seconds: float = Field(default=300.0, gt=0, le=86400, allow_inf_nan=False)
    min_comparison_trades: int = Field(default=50, ge=50, le=1000)
    max_trade_count_reduction: D = Field(default=D(".5"), ge=0, le=D(".5"))
    reserve_fraction_of_search_cpu: D = Field(default=D(".25"), gt=0, le=D(".25"))

    @property
    def policy_hash(self):
        return fingerprint(self)


def verified_result(root, row):
    result = json.loads(row["result_json"])
    path = Path(root) / "artifacts" / (row["experiment_hash"] + ".json")
    if (
        sha256(path) != row["artifact_hash"]
        or fingerprint(result) != row["artifact_hash"]
        or json.loads(path.read_bytes()) != result
        or result.get("integrity_errors")
        or result.get("synthetic") is not True
        or row["status"] == "FAILED_CHECKS"
    ):
        raise ValueError("improvement parent/child artifact integrity mismatch")
    contract = ExperimentContract.model_validate_json(row["contract_json"])
    if any(w.role != "train_only" for w in contract.windows):
        raise ValueError("improvement may not use OOS or holdout")
    return result, contract


def variants(parent, result, limit):
    tags = Counter(
        tag for d in result["diagnostics"] if d["status"] == "MEASURED" for tag in d["tags"]
    )
    candidates = list(children(parent, 4))
    # Order controlled hypotheses by measured evidence, not an assumed remedy.
    if tags["FAST_STOP"]:
        candidates.sort(key=lambda x: x[0].stop_ticks <= parent.stop_ticks)
    elif tags["FAVORABLE_THEN_STOP"]:
        candidates.sort(key=lambda x: x[0].signal.lookback == parent.signal.lookback)
    elif tags["TARGET_NEAR_MISS"]:
        candidates.sort(key=lambda x: x[0].stop_ticks >= parent.stop_ticks)
    if parent.confirmations and len(result["trades"]) < 50:
        raw = parent.model_dump()
        raw["confirmations"] = parent.confirmations[:-1]
        candidates.insert(
            0,
            (
                StrategySpec.model_validate(raw),
                "test whether the last confirmation suppresses training opportunities",
            ),
        )
    seen = {parent.strategy_hash}
    for child, reason in candidates:
        if child.strategy_hash not in seen:
            seen.add(child.strategy_hash)
            yield child, reason
            if len(seen) - 1 >= limit:
                break


def compare(parent, child, policy):
    a, b = metrics(parent["trades"]), metrics(child["trades"])
    parent_keys = {(t["signal"]["available_at"], t["side"]) for t in parent["trades"]}
    child_keys = {(t["signal"]["available_at"], t["side"]) for t in child["trades"]}
    enough = min(a["completed_trades"], b["completed_trades"]) >= policy.min_comparison_trades
    selectivity = b["completed_trades"] < D(a["completed_trades"]) * (
        1 - policy.max_trade_count_reduction
    )
    unresolved = any(
        d["status"] != "MEASURED"
        for result in (parent, child)
        for d in result.get("diagnostics", ())
    ) or any(result.get("open_trade") for result in (parent, child))
    pnl_delta = D(child["ending_equity"]) - D(parent["ending_equity"])
    status = (
        "INCONCLUSIVE"
        if not enough or selectivity or unresolved
        else "TRAIN_IMPROVED_ONLY"
        if pnl_delta > 0
        else "TRAIN_NOT_IMPROVED"
    )
    return status, {
        "parent": a,
        "child": b,
        "ending_equity_delta": str(pnl_delta),
        "common_filled_signal_keys": len(parent_keys & child_keys),
        "parent_only_filled_signal_keys": len(parent_keys - child_keys),
        "child_only_filled_signal_keys": len(child_keys - parent_keys),
        "insufficient_sample": not enough,
        "selectivity_warning": selectivity,
        "censored_or_unresolved": bool(unresolved),
        "independently_validated": False,
        "comparison": "same frozen span/data/cost/risk/engine; entire trade sets retained",
        "warning": "training only; shared entries are descriptive, not a paired significance test",
    }


class Improvement:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def register(self, policy):
        p = Search(self.store, self.root).protocol(policy.search_protocol_hash)
        probe = p.strategy(
            {"lookback": 2, "threshold_tenths": 5, "stop_ticks": 20, "confirmation": "none"}
        )
        require_execution_version(p.contract(probe))
        with self.store.transaction() as db:
            existing = db.execute(
                "SELECT 1 FROM improvement_policies WHERE policy_hash=?", (policy.policy_hash,)
            ).fetchone()
            count = db.execute(
                "SELECT count(*) FROM improvement_controls WHERE enabled=1"
            ).fetchone()[0]
            if not existing and count >= 128:
                raise ValueError("improvement policy capacity: 128 enabled policies")
            db.execute(
                "INSERT OR IGNORE INTO improvement_policies VALUES(?,?,?,?)",
                (policy.policy_hash, serialize(policy), policy.search_protocol_hash, time.time()),
            )
            db.execute(
                "INSERT OR IGNORE INTO improvement_controls VALUES(?,1)", (policy.policy_hash,)
            )
            self.store._audit(
                db, "research", "register_improvement_policy", {"policy_hash": policy.policy_hash}
            )
        return policy.policy_hash

    def disable(self, identity, reason="OPERATOR_DISABLED"):
        with self.store.transaction() as db:
            changed = db.execute(
                "UPDATE improvement_controls SET enabled=0 WHERE policy_hash=?", (identity,)
            )
            if not changed.rowcount:
                raise ValueError("unknown improvement policy")
            self.store._audit(
                db, "research", "improvement_disabled", {"policy_hash": identity, "reason": reason}
            )

    def policies(self):
        rows = self.store.rows("""SELECT p.* FROM improvement_policies p
            JOIN improvement_controls c USING(policy_hash)
            JOIN search_controls s ON s.protocol_hash=p.search_protocol_hash
            WHERE c.enabled=1 AND s.enabled=1 ORDER BY p.created_at,p.policy_hash""")
        return sorted(rows, key=lambda row: (self.used_cpu(row["policy_hash"]), row["policy_hash"]))

    def used_cpu(self, identity):
        rows = self.store.rows(
            """SELECT coalesce(sum(o.cpu_seconds),0) cpu FROM improvement_outcomes o
            JOIN improvement_edges e USING(edge_id) JOIN improvement_plans p USING(plan_hash)
            WHERE p.policy_hash=?""",
            (identity,),
        )
        generation = self.store.rows(
            "SELECT coalesce(sum(generation_cpu_seconds),0) cpu FROM improvement_plans WHERE policy_hash=?",
            (identity,),
        )
        return rows[0]["cpu"] + generation[0]["cpu"]

    def discover(self):
        if self.store.paused():
            return 0
        for policy_row in self.policies():
            policy = ImprovementPolicy.model_validate_json(policy_row["policy_json"])
            identity = policy.policy_hash
            count = self.store.rows(
                "SELECT count(*) n FROM improvement_plans WHERE policy_hash=?", (identity,)
            )[0]["n"]
            if (
                count >= policy.max_parent_plans
                or self.used_cpu(identity) >= policy.cpu_budget_seconds
            ):
                continue
            parents = self.store.rows(
                """SELECT DISTINCT e.* FROM experiments e JOIN search_outcomes o ON o.run_id=e.run_id
                JOIN search_trials t USING(trial_id) WHERE t.protocol_hash=? AND NOT EXISTS
                (SELECT 1 FROM improvement_plans p WHERE p.policy_hash=? AND p.parent_run_id=e.run_id)
                ORDER BY e.created_at,e.run_id LIMIT 1""",
                (policy.search_protocol_hash, identity),
            )
            if not parents:
                continue
            started = time.process_time()
            row = parents[0]
            try:
                result, contract = verified_result(self.root, row)
                require_execution_version(contract)
            except (ValueError, OSError) as exc:
                self.disable(identity, "BLOCKED: " + str(exc)[:1000])
                continue
            parent = StrategySpec.model_validate_json(
                self.store.rows(
                    "SELECT spec_json FROM strategy_specs WHERE strategy_id=?",
                    (row["strategy_id"],),
                )[0]["spec_json"]
            )
            p = Search(self.store, self.root).protocol(policy.search_protocol_hash)
            if (
                contract.dataset_hash != p.dataset_hash
                or contract.instrument_hash != fingerprint(p.profile)
                or contract.windows != (p.window,)
            ):
                raise ValueError("improvement parent is outside its authorized training region")
            summary = metrics(result["trades"])
            tags = Counter(
                tag for d in result["diagnostics"] if d["status"] == "MEASURED" for tag in d["tags"]
            )
            unmet = (
                not result["trades"]
                or summary["win_rate"] < 0.7
                or summary["max_losing_streak"] > 5
                or D(result["ending_equity"]) < 500
                or summary["completed_trades"] < 50
            )
            proposed = (
                list(variants(parent, result, policy.max_children))
                if unmet and result["trades"]
                else []
            )
            evidence = {
                "parent_artifact_sha256": row["artifact_hash"],
                "diagnostic_tags": dict(tags),
                "metrics": summary,
                "diagnostic_goals_unmet": unmet,
                "decision": "BOUNDED_CONTROLLED_CHILDREN" if proposed else "RETAIN_NO_MUTATION",
                "reason": "training diagnostic goals only; no independent selection evidence",
                "parent_has_closed_trades": bool(result["trades"]),
            }
            plan_hash = fingerprint(
                {"policy": identity, "parent_run_id": row["run_id"], "evidence": evidence}
            )
            # All edges are committed with their plan. A crash before this transaction
            # cannot leave a plan that permanently lost its children.
            with self.store.transaction() as db:
                db.execute(
                    "INSERT OR IGNORE INTO improvement_plans VALUES(?,?,?,?,?,?)",
                    (
                        plan_hash,
                        identity,
                        row["run_id"],
                        serialize(evidence),
                        time.process_time() - started,
                        time.time(),
                    ),
                )
                for child, reason in proposed:
                    changed = [
                        k for k, v in child.model_dump().items() if parent.model_dump()[k] != v
                    ]
                    db.execute(
                        "INSERT OR IGNORE INTO strategy_specs VALUES(?,?,?,?,?,?)",
                        (
                            child.strategy_hash,
                            serialize(child),
                            parent.strategy_hash,
                            reason,
                            serialize(changed),
                            time.time(),
                        ),
                    )
                    child_contract = ExperimentContract.model_validate(
                        {**contract.model_dump(), "strategy_hash": child.strategy_hash}
                    )
                    edge_id = fingerprint(
                        {"plan": plan_hash, "child": child_contract.experiment_hash}
                    )
                    payload = {
                        "strategy": child.model_dump(mode="json"),
                        "contract": child_contract.model_dump(mode="json"),
                        "profile": p.profile.model_dump(mode="json"),
                        "screening": SCREEN_POLICY,
                        "improvement_edge_id": edge_id,
                    }
                    db.execute(
                        "INSERT OR IGNORE INTO improvement_edges VALUES(?,?,?,?,?,?,?,?)",
                        (
                            edge_id,
                            plan_hash,
                            child.strategy_hash,
                            child_contract.experiment_hash,
                            serialize(payload),
                            reason,
                            serialize(changed),
                            time.time(),
                        ),
                    )
                self.store._audit(
                    db,
                    "research",
                    "improvement_plan",
                    {"plan_hash": plan_hash, "children": len(proposed)},
                )
            return 1
        return 0

    def admit(self):
        if (
            self.store.paused()
            or self.store.rows("""SELECT 1 FROM jobs WHERE
            state IN ('QUEUED','RUNNING','FAILED_RETRYABLE') AND json_extract(payload,'$.improvement_edge_id') IS NOT NULL LIMIT 1""")
        ):
            return 0
        for row in self.policies():
            policy = ImprovementPolicy.model_validate_json(row["policy_json"])
            used = self.used_cpu(policy.policy_hash)
            search_cpu = self.store.rows(
                """SELECT coalesce(sum(o.cpu_seconds),0) cpu FROM search_outcomes o
                JOIN search_trials t USING(trial_id) WHERE t.protocol_hash=?""",
                (policy.search_protocol_hash,),
            )[0]["cpu"]
            # An initial one-second credit permits the first measurement. Limits
            # are checked between jobs, so a single native job can overshoot.
            if used >= min(
                policy.cpu_budget_seconds,
                max(1, search_cpu * float(policy.reserve_fraction_of_search_cpu)),
            ):
                continue
            edges = self.store.rows(
                """SELECT e.* FROM improvement_edges e JOIN improvement_plans p USING(plan_hash)
                LEFT JOIN improvement_outcomes o USING(edge_id) LEFT JOIN jobs j ON j.idempotency_key=e.child_experiment_hash
                WHERE p.policy_hash=? AND o.edge_id IS NULL AND j.job_id IS NULL ORDER BY e.created_at,e.edge_id LIMIT 1""",
                (policy.policy_hash,),
            )
            if edges:
                edge = edges[0]
                payload = json.loads(edge["payload_json"])
                try:
                    require_execution_version(
                        ExperimentContract.model_validate(payload["contract"])
                    )
                except ValueError as exc:
                    self.disable(policy.policy_hash, "BLOCKED: " + str(exc)[:1000])
                    return 0
                self.store.enqueue(
                    "research",
                    payload,
                    edge["child_experiment_hash"],
                    actor="controlled-improvement",
                )
                return 1
        return 0

    def feedback(self):
        edges = self.store.rows("""SELECT e.*,p.parent_run_id,p.policy_hash,r.policy_json FROM improvement_edges e
            JOIN improvement_plans p USING(plan_hash) JOIN improvement_policies r USING(policy_hash)
            JOIN jobs j ON j.idempotency_key=e.child_experiment_hash
            LEFT JOIN improvement_outcomes o USING(edge_id) WHERE o.edge_id IS NULL
            AND j.state IN ('COMPLETED','FAILED_FINAL','CANCELLED')
            ORDER BY j.updated_at,e.edge_id LIMIT 64""")
        applied = 0
        for edge in edges:
            jobs = self.store.rows(
                "SELECT * FROM jobs WHERE idempotency_key=?", (edge["child_experiment_hash"],)
            )
            if not jobs or jobs[0]["state"] not in ("COMPLETED", "FAILED_FINAL", "CANCELLED"):
                continue
            job = jobs[0]
            attempts = self.store.rows(
                "SELECT r.resources_json FROM attempt_resources r JOIN attempts a USING(token) WHERE a.job_id=?",
                (job["job_id"],),
            )
            # Reused exact jobs are not charged twice.
            cpu = (
                sum(json.loads(a["resources_json"])["cpu_seconds"] for a in attempts)
                if (
                    json.loads(job["payload"]).get("improvement_edge_id") == edge["edge_id"]
                    and job["created_at"] >= edge["created_at"]
                )
                else 0
            )
            parent_row = self.store.rows(
                "SELECT * FROM experiments WHERE run_id=?", (edge["parent_run_id"],)
            )[0]
            parent, parent_contract = verified_result(self.root, parent_row)
            children_rows = self.store.rows(
                "SELECT * FROM experiments WHERE experiment_hash=?",
                (edge["child_experiment_hash"],),
            )
            status, evidence = (
                "FAILED_CHECKS",
                {"error": job["error"] or "NO_VERIFIED_NATIVE_RESULT"},
            )
            if children_rows:
                child, child_contract = verified_result(self.root, children_rows[0])
                a, b = parent_contract.model_dump(), child_contract.model_dump()
                a.pop("strategy_hash")
                b.pop("strategy_hash")
                if a != b:
                    raise ValueError("paired improvement contract mismatch")
                status, evidence = compare(
                    parent, child, ImprovementPolicy.model_validate_json(edge["policy_json"])
                )
                evidence["parent_run_id"] = parent_row["run_id"]
                evidence["child_run_id"] = children_rows[0]["run_id"]
            elif job["state"] == "COMPLETED":
                verify_pruned(
                    self.root,
                    json.loads(edge["payload_json"])["contract"],
                    json.loads(job["result"]),
                )
                status, evidence = (
                    "INCONCLUSIVE",
                    {"reason": "EXACT_NO_SIGNALS_TIER0", "independently_validated": False},
                )
            evidence["multiple_comparison_children_at_decision"] = self.store.rows(
                "SELECT count(*) n FROM improvement_edges"
            )[0]["n"]
            with self.store.transaction() as db:
                inserted = db.execute(
                    "INSERT OR IGNORE INTO improvement_outcomes VALUES(?,?,?,?,?)",
                    (edge["edge_id"], status, serialize(evidence), cpu, time.time()),
                )
                if inserted.rowcount:
                    spec = StrategySpec.model_validate(json.loads(edge["payload_json"])["strategy"])
                    db.execute(
                        "UPDATE research_coverage SET cpu_seconds=cpu_seconds+? WHERE instrument=? AND family=? AND timeframe=?",
                        (cpu, spec.instrument, spec.signal.operator, spec.timeframe),
                    )
                    self.store._audit(
                        db,
                        "research",
                        "improvement_feedback",
                        {"edge_id": edge["edge_id"], "status": status},
                    )
            applied += 1
        return applied

    def status(self):
        return {
            "scope": "bounded registered-region training improvement; no independent validation",
            "paused": self.store.paused(),
            "policies": self.store.rows(
                "SELECT p.*,c.enabled FROM improvement_policies p JOIN improvement_controls c USING(policy_hash) ORDER BY p.created_at DESC,p.policy_hash LIMIT 200"
            ),
            "plans": self.store.rows("SELECT count(*) count FROM improvement_plans")[0]["count"],
            "children": self.store.rows("SELECT count(*) count FROM improvement_edges")[0]["count"],
            "outcomes": self.store.rows(
                "SELECT status,count(*) count FROM improvement_outcomes GROUP BY status"
            ),
            "measured_worker_cpu_seconds": self.store.rows(
                "SELECT coalesce(sum(cpu_seconds),0) cpu FROM improvement_outcomes"
            )[0]["cpu"],
            "limitations": [
                "single bounded round per parent/policy; no automatic recursive descent",
                "no independent OOS/WFO promotion here",
                "CPU limits checked between jobs; one job can overshoot",
                "full regime/session cohort diagnostics still incomplete",
            ],
        }
