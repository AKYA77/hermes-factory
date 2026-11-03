"""Persistent source-window influence records and protected final holdouts.

The managed-state trust boundary is explicit: external inspection must be
owner-declared. Dataset aliases/revisions cannot bypass instrument/time guards.
"""

import json
from pathlib import Path
import time
from typing import Literal

from pydantic import Field, model_validator

from factory.contracts import (
    Contract,
    ExperimentContract,
    InstrumentSpec,
    StrategySpec,
    Window,
    fingerprint,
    serialize,
)
from factory.data import Catalog, sha256
from factory.provenance import execution_revision
from factory.simulation.ledger import require_execution_version


def evidence_kind(profile):
    return "synthetic" if profile.synthetic else "historical"


def check_access(db, instrument, kind, start, end, authorization=None, contract=None):
    reservations = db.execute(
        """SELECT * FROM protected_holdouts WHERE instrument=? AND evidence_kind=?
        AND start_ns<? AND end_ns>?""",
        (instrument, kind, end, start),
    ).fetchall()
    for reservation in reservations:
        allowed = db.execute(
            """SELECT * FROM holdout_consumptions WHERE holdout_id=?
            AND authorization_id=? AND contract_json=?""",
            (
                reservation["holdout_id"],
                authorization or "",
                serialize(contract) if contract else "",
            ),
        ).fetchone()
        if not allowed:
            raise ValueError("PROTECTED_HOLDOUT_ACCESS: " + reservation["holdout_id"])


def record_use(
    db, instrument, kind, dataset, start, end, purpose, owner, *, authorization=None, contract=None
):
    check_access(db, instrument, kind, start, end, authorization, contract)
    identity = fingerprint(
        {
            "instrument": instrument,
            "kind": kind,
            "dataset": dataset,
            "start": start,
            "end": end,
            "purpose": purpose,
            "owner": owner,
        }
    )
    db.execute(
        "INSERT OR IGNORE INTO research_input_uses VALUES(?,?,?,?,?,?,?,?,?)",
        (identity, instrument, kind, dataset, start, end, purpose, owner, time.time()),
    )
    return identity


def training_use(db, profile, contract, owner, purpose="training"):
    if any(w.role != "train_only" for w in contract.windows):
        raise ValueError("training access may not consume evaluation windows")
    for w in contract.windows:
        record_use(
            db,
            profile.instrument,
            evidence_kind(profile),
            contract.dataset_hash,
            w.start_ns,
            w.end_ns,
            purpose,
            owner,
        )


class HoldoutSpec(Contract):
    schema_version: Literal["protected-holdout/v1"] = "protected-holdout/v1"
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: InstrumentSpec
    window: Window
    code_revision: str
    external_use_declaration: Literal["NO_PRIOR_USE_DECLARED"]
    declaration_notes: str = Field(min_length=8, max_length=2000)

    @model_validator(mode="after")
    def final_window(self):
        if self.window.role != "final_holdout_unseen":
            raise ValueError("protected holdout requires final_holdout_unseen")
        return self

    @property
    def holdout_id(self):
        return fingerprint(self)


class Holdouts:
    def __init__(self, root):
        from factory.experiments import Store

        self.root = Path(root)
        self.store = Store(self.root / "factory.sqlite")

    def register(self, spec):
        if spec.code_revision != execution_revision():
            raise ValueError("holdout source revision mismatch")
        m = Catalog(self.root / "catalog").verify(spec.dataset_hash, deep=True)
        w, p = spec.window, spec.profile
        if (
            m["instrument"] != p.instrument
            or bool(m["provenance"].get("synthetic")) != p.synthetic
            or w.start_ns < m["first_ns"]
            or w.end_ns > m["latest_verified_ns"] + 1
        ):
            raise ValueError("holdout dataset/profile/bounds mismatch")
        kind = evidence_kind(p)
        with self.store.transaction() as db:
            existing = db.execute(
                "SELECT spec_json FROM protected_holdouts WHERE holdout_id=?", (spec.holdout_id,)
            ).fetchone()
            if existing:
                if existing[0] != serialize(spec):
                    raise ValueError("holdout identity collision")
                return spec.holdout_id
            if db.execute(
                """SELECT 1 FROM protected_holdouts WHERE instrument=? AND evidence_kind=?
                AND start_ns<? AND end_ns>? LIMIT 1""",
                (p.instrument, kind, w.end_ns, w.start_ns),
            ).fetchone():
                raise ValueError("overlapping final holdout reservation")
            if db.execute(
                """SELECT 1 FROM research_input_uses WHERE instrument=? AND evidence_kind=?
                AND start_ns<? AND end_ns>? LIMIT 1""",
                (p.instrument, kind, w.end_ns, w.start_ns),
            ).fetchone():
                raise ValueError("HOLDOUT_ALREADY_INFLUENCED: recorded research input")
            # Include pre-migration history. These predicates conservatively treat
            # registration/enqueue as potential influence, not proof of success.
            protocols = db.execute(
                """SELECT 1 FROM search_protocols WHERE
                json_extract(protocol_json,'$.profile.instrument')=? AND
                json_extract(protocol_json,'$.profile.synthetic')=? AND
                json_extract(protocol_json,'$.window.start_ns')<? AND
                json_extract(protocol_json,'$.window.end_ns')>? LIMIT 1""",
                (p.instrument, int(p.synthetic), w.end_ns, w.start_ns),
            ).fetchone()
            jobs = db.execute(
                """SELECT 1 FROM jobs j,json_each(j.payload,'$.contract.windows') x WHERE
                json_extract(j.payload,'$.profile.instrument')=? AND json_extract(j.payload,'$.profile.synthetic')=?
                AND json_extract(x.value,'$.start_ns')<? AND json_extract(x.value,'$.end_ns')>? LIMIT 1""",
                (p.instrument, int(p.synthetic), w.end_ns, w.start_ns),
            ).fetchone()
            runs = db.execute(
                """SELECT 1 FROM experiments e,json_each(e.contract_json,'$.windows') x WHERE
                e.instrument=? AND coalesce(json_extract(e.result_json,'$.synthetic'),?)=?
                AND json_extract(x.value,'$.start_ns')<? AND json_extract(x.value,'$.end_ns')>? LIMIT 1""",
                (p.instrument, int(p.synthetic), int(p.synthetic), w.end_ns, w.start_ns),
            ).fetchone()
            if protocols or jobs or runs:
                raise ValueError("HOLDOUT_ALREADY_INFLUENCED: legacy protocol/job/result")
            db.execute(
                "INSERT INTO protected_holdouts VALUES(?,?,?,?,?,?,?,?)",
                (
                    spec.holdout_id,
                    serialize(spec),
                    p.instrument,
                    kind,
                    spec.dataset_hash,
                    w.start_ns,
                    w.end_ns,
                    time.time(),
                ),
            )
            self.store._audit(db, "validation", "holdout_reserved", {"holdout_id": spec.holdout_id})
        return spec.holdout_id

    def spec(self, identity):
        rows = self.store.rows(
            "SELECT spec_json FROM protected_holdouts WHERE holdout_id=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown protected holdout")
        spec = HoldoutSpec.model_validate_json(rows[0]["spec_json"])
        if spec.holdout_id != identity:
            raise ValueError("holdout identity mismatch")
        return spec

    def freeze(self, identity, training_run_id):
        spec = self.spec(identity)
        rows = self.store.rows(
            """SELECT e.*,s.spec_json FROM experiments e
            JOIN strategy_specs s ON s.strategy_id=e.strategy_id WHERE e.run_id=?""",
            (training_run_id,),
        )
        if not rows:
            raise ValueError("verified training experiment required")
        row = rows[0]
        training = ExperimentContract.model_validate_json(row["contract_json"])
        require_execution_version(training)
        result = json.loads(row["result_json"])
        artifact = self.root / "artifacts" / (training_run_id + ".json")
        if (
            row["experiment_hash"] != training.experiment_hash
            or fingerprint(result) != row["artifact_hash"]
            or sha256(artifact) != row["artifact_hash"]
            or json.loads(artifact.read_bytes()) != result
            or result.get("integrity_errors")
            or row["status"] == "FAILED_CHECKS"
        ):
            raise ValueError("training artifact integrity mismatch")
        if (
            training.dataset_hash != spec.dataset_hash
            or training.instrument_hash != fingerprint(spec.profile)
            or training.code_revision != spec.code_revision
            or not training.windows
            or any(
                w.role != "train_only" or w.end_ns > spec.window.start_ns for w in training.windows
            )
        ):
            raise ValueError("candidate must use only preceding authorized training")
        strategy = StrategySpec.model_validate_json(row["spec_json"])
        if strategy.strategy_hash != training.strategy_hash:
            raise ValueError("training strategy identity mismatch")
        contract = ExperimentContract.model_validate(
            {
                **training.model_dump(),
                "windows": (spec.window,),
                "evaluation_policy": "protected-confirmation/v1",
            }
        )
        payload = {
            "contract": contract.model_dump(mode="json"),
            "strategy": strategy.model_dump(mode="json"),
            "profile": spec.profile.model_dump(mode="json"),
            "holdout_id": identity,
        }
        with self.store.transaction() as db:
            previous = db.execute(
                "SELECT training_run_id,payload_json FROM holdout_selections WHERE holdout_id=?",
                (identity,),
            ).fetchone()
            if previous and tuple(previous) != (training_run_id, serialize(payload)):
                raise ValueError("immutable holdout candidate selection")
            db.execute(
                "INSERT OR IGNORE INTO holdout_selections VALUES(?,?,?,?)",
                (identity, training_run_id, serialize(payload), time.time()),
            )
            self.store._audit(
                db,
                "validation",
                "holdout_candidate_frozen",
                {"holdout_id": identity, "training_run_id": training_run_id},
            )
        return payload

    def authorize(self, identity):
        rows = self.store.rows(
            "SELECT payload_json FROM holdout_selections WHERE holdout_id=?", (identity,)
        )
        if not rows:
            raise ValueError("freeze verified candidate before consuming holdout")
        payload = json.loads(rows[0]["payload_json"])
        contract = ExperimentContract.model_validate(payload["contract"])
        require_execution_version(contract)
        authorization = fingerprint(
            {
                "version": "holdout-consumption/v1",
                "holdout_id": identity,
                "contract_hash": contract.experiment_hash,
            }
        )
        with self.store.transaction() as db:
            previous = db.execute(
                "SELECT authorization_id,contract_json FROM holdout_consumptions WHERE holdout_id=?",
                (identity,),
            ).fetchone()
            if previous and tuple(previous) != (authorization, serialize(contract)):
                raise ValueError("holdout already consumed by a different evaluation")
            db.execute(
                "INSERT OR IGNORE INTO holdout_consumptions VALUES(?,?,?,?)",
                (identity, authorization, serialize(contract), time.time()),
            )
            self.store._audit(
                db,
                "validation",
                "holdout_consumed_before_execution",
                {
                    "holdout_id": identity,
                    "authorization_id": authorization,
                    "repeat_same_evaluation": bool(previous),
                },
            )
        return {**payload, "holdout_authorization": authorization}

    def enqueue(self, identity):
        payload = self.authorize(identity)
        contract = ExperimentContract.model_validate(payload["contract"])
        job_id = self.store.enqueue(
            "validation", payload, contract.experiment_hash, actor="validation"
        )
        return {
            "job_id": job_id,
            "evaluation_id": contract.experiment_hash,
            "holdout_id": identity,
            "state": "CONSUMED_ON_ATTEMPT",
            "independent_observation_id": payload["holdout_authorization"],
        }

    def status(self, limit=50, offset=0):
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("invalid holdout page")
        return self.store.rows(
            """SELECT h.*,s.training_run_id,c.authorization_id,
            CASE WHEN c.holdout_id IS NOT NULL THEN 'HOLDOUT_CONSUMED'
                 WHEN s.holdout_id IS NOT NULL THEN 'CANDIDATE_FROZEN' ELSE 'RESERVED_UNSEEN' END status
            FROM protected_holdouts h LEFT JOIN holdout_selections s USING(holdout_id)
            LEFT JOIN holdout_consumptions c USING(holdout_id) ORDER BY h.created_at,h.holdout_id LIMIT ? OFFSET ?""",
            (limit, offset),
        )


def evaluation_use(db, profile, contract, manifest, payload):
    authorization = payload.get("holdout_authorization")
    if any(w.role == "final_holdout_unseen" for w in contract.windows):
        if len(contract.windows) != 1 or not authorization:
            raise ValueError("final holdout requires one frozen authorized evaluation")
        row = db.execute(
            """SELECT h.holdout_id FROM holdout_consumptions c
            JOIN protected_holdouts h USING(holdout_id) WHERE c.authorization_id=?
            AND c.contract_json=? AND h.holdout_id=?""",
            (authorization, serialize(contract), payload.get("holdout_id", "")),
        ).fetchone()
        if not row:
            raise ValueError("unknown or mismatched holdout authorization")
    for window in contract.windows:
        record_use(
            db,
            profile.instrument,
            evidence_kind(profile),
            contract.dataset_hash,
            manifest["first_ns"],
            window.end_ns,
            "evaluation-with-past-only-warmup",
            contract.experiment_hash,
            authorization=authorization,
            contract=contract,
        )
