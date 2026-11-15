"""Persistent fail-closed screen circuit breaker and bounded native rechecks.

Original negative evidence and scientific outcomes are never rewritten. A new
queue job references each original rejection, retaining its exact contract.
"""

import json
import re

from factory.contracts import ExperimentContract, fingerprint, serialize
from factory.provenance import execution_revision

KEY = "tier0_circuit_breaker"
MAX_RECHECKS = 64
MAX_RECHECK_CPU_SECONDS = 300


def status(store):
    row = store.rows("SELECT value FROM controls WHERE key=?", (KEY,))
    if not row:
        return {"enabled": True, "incident": None, "reason": None}
    try:
        value = json.loads(row[0]["value"])
        if value["enabled"] is not False or not re.fullmatch(r"[a-f0-9]{64}", value["incident"]):
            raise ValueError("invalid breaker")
        return value
    except (ValueError, KeyError, TypeError):
        return {"enabled": False, "incident": None, "reason": "CORRUPT_BREAKER_FAIL_CLOSED"}


def trip(store, contract, evidence_hash):
    contract = ExperimentContract.model_validate(contract)
    if not re.fullmatch(r"[a-f0-9]{64}", evidence_hash):
        raise ValueError("invalid screen failure evidence")
    body = {
        "schema_version": "screen-circuit-breaker/v1",
        "experiment_hash": contract.experiment_hash,
        "code_revision": contract.code_revision,
        "evidence_hash": evidence_hash,
        "reason": "TIER0_FALSE_NEGATIVE",
        "effect": "Disable exact-zero pruning; retain native evaluation and immutable prior evidence",
    }
    identity = fingerprint(body)
    with store.transaction() as db:
        previous = db.execute("SELECT value FROM controls WHERE key=?", (KEY,)).fetchone()
        if previous:
            return False
        db.execute(
            "INSERT INTO controls VALUES(?,?)",
            (KEY, serialize({"enabled": False, "incident": identity, "reason": body["reason"]})),
        )
        store._audit(
            db,
            "native-screen-audit",
            "tier0_circuit_breaker_tripped",
            {"incident": identity, **body},
        )
    return True


def recovery_budget(store):
    count = store.rows("SELECT count(*) n FROM jobs WHERE idempotency_key LIKE 'screen-recheck:%'")[
        0
    ]["n"]
    cpu = store.rows("""SELECT coalesce(sum(json_extract(r.resources_json,'$.cpu_seconds')),0) cpu
        FROM attempt_resources r JOIN attempts a USING(token) JOIN jobs j USING(job_id)
        WHERE j.idempotency_key LIKE 'screen-recheck:%'""")[0]["cpu"]
    return {
        "policy": "native-recheck-budget/v1",
        "admitted": count,
        "max_rechecks": MAX_RECHECKS,
        "measured_cpu_seconds": cpu,
        "max_cpu_seconds": MAX_RECHECK_CPU_SECONDS,
        "admission_stopped": count >= MAX_RECHECKS or cpu >= MAX_RECHECK_CPU_SECONDS,
        "scope": "Admission guards; bounded in-flight work may finish. No automatic budget reset.",
    }


def enqueue_rechecks(store, root, max_queued=2):
    """At most the ordinary queue capacity; never resume or rewrite contracts.

    Old-code rejections remain visible but cannot execute under a different
    revision. This function grants no new data/holdout permission.
    """
    if store.paused() or status(store)["enabled"]:
        return 0
    active = store.rows(
        "SELECT count(*) n FROM jobs WHERE state IN ('QUEUED','RUNNING','FAILED_RETRYABLE')"
    )[0]["n"]
    budget = recovery_budget(store)
    if budget["admission_stopped"]:
        return 0
    capacity = min(2, MAX_RECHECKS - budget["admitted"], max(0, max_queued - active))
    if not capacity:
        return 0
    revision = execution_revision()
    rows = store.rows(
        """SELECT j.job_id,j.payload FROM jobs j
        WHERE j.state='COMPLETED' AND j.kind='research'
        AND json_extract(j.result,'$.screen.decision')='PRUNE_NO_SIGNALS'
        AND json_extract(j.payload,'$.contract.code_revision')=?
        AND NOT EXISTS(SELECT 1 FROM experiments e WHERE e.experiment_hash=json_extract(j.result,'$.screen.experiment_hash'))
        AND NOT EXISTS(SELECT 1 FROM jobs r WHERE r.idempotency_key='screen-recheck:'||j.job_id)
        ORDER BY j.created_at,j.job_id LIMIT ?""",
        (revision, capacity),
    )
    incident = status(store)["incident"]
    for row in rows:
        payload = json.loads(row["payload"])
        payload["screen_recheck_of"] = row["job_id"]
        payload["screen_recheck_incident"] = incident
        # Worker reads the persistent breaker itself. Preserve requested policy,
        # especially for cost-shadow contracts that require its explicit marker.
        store.enqueue(
            "research",
            payload,
            "screen-recheck:" + row["job_id"],
            actor="native-screen-recovery",
            priority=20,
        )
    return len(rows)
