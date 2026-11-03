"""Recurring, offline training-research admission and outcome feedback.

Registered protocols are explicit authorized regions, not inferred holdouts.
Paused installations and installations without protocols generate no work.
One bounded heavy job at a time remains the process model.
"""

import json
import time
from factory.contracts import ExperimentContract
from factory.exploration.persistent import Search
from factory.screening import SCREEN_POLICY


def maintenance(store, root, max_queued=2):
    search = Search(store, root)
    applied = search.feedback()
    if store.paused():
        return {"feedback": applied, "proposed": 0}
    # Recover durable proposals first. Existing experiment IDs are reused by the
    # unique queue key; retries are not new parameter trials or full replays.
    active = store.rows(
        "SELECT count(*) n FROM jobs WHERE state IN ('QUEUED','RUNNING','FAILED_RETRYABLE')"
    )[0]["n"]
    for row in search.pending():
        if active >= max_queued:
            break
        if not search.ready_to_enqueue(row):
            continue
        protocol = search.protocol(row["protocol_hash"])
        contract = ExperimentContract.model_validate_json(row["contract_json"])
        if store.rows("SELECT 1 FROM jobs WHERE idempotency_key=?", (contract.experiment_hash,)):
            continue
        store.enqueue(
            "research",
            {
                "strategy": json.loads(row["spec_json"]),
                "contract": json.loads(row["contract_json"]),
                "profile": protocol.profile.model_dump(mode="json"),
                "screening": SCREEN_POLICY,
            },
            contract.experiment_hash,
            actor="research-recovery",
        )
        active += 1
    if active >= max_queued:
        return {"feedback": applied, "proposed": 0}
    # Charge actual measured CPU to instruments/cells, with proposal CPU included.
    # A stable trial-count tie-break reserves breadth before objective exploitation.
    cells = store.rows("""SELECT p.*,coalesce(sum(coalesce(o.cpu_seconds,0)+t.generation_cpu_seconds),0) cpu,
        count(t.trial_id) trials FROM search_protocols p JOIN search_controls c USING(protocol_hash)
        LEFT JOIN search_trials t USING(protocol_hash) LEFT JOIN search_outcomes o USING(trial_id)
        WHERE c.enabled=1 GROUP BY p.protocol_hash""")
    instrument_cpu = {}
    for cell in cells:
        symbol = json.loads(cell["protocol_json"])["profile"]["instrument"]
        instrument_cpu[symbol] = instrument_cpu.get(symbol, 0) + cell["cpu"]
    cells.sort(
        key=lambda cell: (
            instrument_cpu[json.loads(cell["protocol_json"])["profile"]["instrument"]],
            cell["cpu"],
            cell["trials"],
            cell["protocol_hash"],
        )
    )
    for cell in cells:
        try:
            trial = search.ask(cell["protocol_hash"])
        except ValueError as exc:
            # Scientific source changes never silently rebase a protocol or reuse
            # its supposedly independent window. Owner registers a new version.
            if "source revision mismatch" not in str(exc):
                raise
            with store.transaction() as db:
                db.execute(
                    "UPDATE search_controls SET enabled=0,reason=?,updated_at=? WHERE protocol_hash=?",
                    ("STALE_SOURCE", time.time(), cell["protocol_hash"]),
                )
                store._audit(
                    db,
                    "research",
                    "protocol_disabled",
                    {"protocol_hash": cell["protocol_hash"], "reason": "STALE_SOURCE"},
                )
            continue
        if trial:
            if not trial["duplicate"]:
                protocol = search.protocol(cell["protocol_hash"])
                store.enqueue(
                    "research",
                    {
                        "strategy": trial["spec"].model_dump(mode="json"),
                        "contract": trial["contract"].model_dump(mode="json"),
                        "profile": protocol.profile.model_dump(mode="json"),
                        "screening": SCREEN_POLICY,
                    },
                    trial["contract"].experiment_hash,
                    actor="research",
                )
            return {"feedback": applied, "proposed": 1, "trial_id": trial["trial_id"]}
    return {"feedback": applied, "proposed": 0}
