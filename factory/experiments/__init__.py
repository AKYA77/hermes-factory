"""Durable local single-writer store, immutable results and fenced leases."""

from contextlib import contextmanager, closing
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid

from factory.contracts import SYMBOLS, TIMEFRAMES, serialize, fingerprint


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            for migration in sorted(self._migration().parent.glob("[0-9][0-9][0-9]_*.sql")):
                db.executescript(migration.read_text())
            db.executemany(
                "INSERT OR IGNORE INTO research_coverage(instrument,family,timeframe) VALUES(?,?,?)",
                [
                    (s, f, t)
                    for s in SYMBOLS
                    for f in ("mean_reversion", "momentum", "breakout")
                    for t in TIMEFRAMES
                ],
            )

    @staticmethod
    def _migration():
        path = Path(__file__).parents[2] / "migrations/001_initial.sql"
        return path if path.exists() else Path(__file__).parents[1] / "sql/001_initial.sql"

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, params=()):
        with closing(self.connect()) as db:
            return [dict(r) for r in db.execute(sql, params)]

    def audit(self, actor, action, payload):
        with self.transaction() as db:
            self._audit(db, actor, action, payload)

    @staticmethod
    def _audit(db, actor, action, payload):
        db.execute(
            "INSERT INTO audit_events(actor,action,payload,created_at) VALUES(?,?,?,?)",
            (actor, action, serialize(payload), time.time()),
        )

    def paused(self):
        return self.rows("SELECT value FROM controls WHERE key='paused'")[0]["value"] == "true"

    def pause(self, paused, actor):
        with self.transaction() as db:
            db.execute(
                "UPDATE controls SET value=? WHERE key='paused'", ("true" if paused else "false",)
            )
            self._audit(db, actor, "pause" if paused else "resume", {})

    def register_strategy(self, spec, parent=None, hypothesis=None):
        changed = []
        with self.transaction() as db:
            if parent:
                old = db.execute(
                    "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (parent,)
                ).fetchone()
                if old is None:
                    raise ValueError("unknown parent")
                old = json.loads(old[0])
                new = json.loads(serialize(spec))
                changed = [k for k in new if new[k] != old[k]]
                if not changed or not hypothesis:
                    raise ValueError("child requires changed fields and hypothesis")
            db.execute(
                "INSERT OR IGNORE INTO strategy_specs VALUES(?,?,?,?,?,?)",
                (
                    spec.strategy_hash,
                    serialize(spec),
                    parent,
                    hypothesis,
                    serialize(changed),
                    time.time(),
                ),
            )
        return spec.strategy_hash

    def enqueue(self, kind, payload, key, actor="coordinator", priority=50, max_attempts=3):
        now = time.time()
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO jobs(job_id,idempotency_key,kind,payload,priority,max_attempts,available_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    key,
                    kind,
                    serialize(payload),
                    priority,
                    max_attempts,
                    now,
                    now,
                    now,
                ),
            )
            row = db.execute("SELECT job_id FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
            self._audit(db, actor, "enqueue", {"job_id": row[0], "kind": kind})
            return row[0]

    def claim(self, lease_seconds=120, now=None, *, respect_pause=False):
        now = time.time() if now is None else now
        with self.transaction() as db:
            if (
                respect_pause
                and db.execute("SELECT value FROM controls WHERE key='paused'").fetchone()[0]
                == "true"
            ):
                return None
            expired = db.execute(
                "SELECT job_id,lease_token,attempts,max_attempts FROM jobs WHERE state='RUNNING' AND lease_until<=?",
                (now,),
            ).fetchall()
            for j in expired:
                db.execute(
                    "UPDATE attempts SET ended_at=?,outcome='LEASE_EXPIRED' WHERE token=? AND ended_at IS NULL",
                    (now, j["lease_token"]),
                )
                db.execute(
                    "UPDATE jobs SET state=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE job_id=?",
                    (
                        "FAILED_FINAL" if j["attempts"] >= j["max_attempts"] else "QUEUED",
                        now,
                        j["job_id"],
                    ),
                )
            j = db.execute(
                "SELECT * FROM jobs WHERE state IN ('QUEUED','FAILED_RETRYABLE') AND available_at<=? ORDER BY priority,created_at,job_id LIMIT 1",
                (now,),
            ).fetchone()
            if j is None:
                return None
            token = str(uuid.uuid4())
            db.execute(
                "UPDATE jobs SET state='RUNNING',attempts=attempts+1,lease_token=?,lease_until=?,updated_at=? WHERE job_id=?",
                (token, now + lease_seconds, now, j["job_id"]),
            )
            db.execute(
                "INSERT INTO attempts(job_id,token,started_at) VALUES(?,?,?)",
                (j["job_id"], token, now),
            )
            return dict(db.execute("SELECT * FROM jobs WHERE job_id=?", (j["job_id"],)).fetchone())

    def heartbeat(self, job_id, token, seconds=120):
        now = time.time()
        with self.transaction() as db:
            n = db.execute(
                "UPDATE jobs SET lease_until=?,updated_at=? WHERE job_id=? AND lease_token=? AND state='RUNNING' AND lease_until>?",
                (now + seconds, now, job_id, token, now),
            ).rowcount
            if not n:
                raise ValueError("STALE_LEASE")

    @staticmethod
    def _resources(db, token, value):
        if value is None:
            return
        if not all(
            isinstance(value.get(k), (int, float)) and math.isfinite(value[k]) and value[k] >= 0
            for k in ("cpu_seconds", "wall_seconds")
        ):
            raise ValueError("invalid measured resources")
        db.execute(
            "INSERT INTO attempt_resources VALUES(?,?,?)", (token, serialize(value), time.time())
        )

    def finish(self, job_id, token, result=None, error=None, retryable=False):
        now = time.time()
        with self.transaction() as db:
            j = db.execute(
                "SELECT * FROM jobs WHERE job_id=? AND lease_token=? AND state='RUNNING' AND lease_until>?",
                (job_id, token, now),
            ).fetchone()
            if j is None:
                raise ValueError("STALE_LEASE")
            self._resources(db, token, (result or {}).get("resources"))
            state = (
                "COMPLETED"
                if error is None
                else "FAILED_RETRYABLE"
                if retryable and j["attempts"] < j["max_attempts"]
                else "FAILED_FINAL"
            )
            db.execute(
                "UPDATE jobs SET state=?,result=?,error=?,available_at=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE job_id=?",
                (state, serialize(result), error, now + min(3600, 2 ** j["attempts"]), now, job_id),
            )
            db.execute(
                "UPDATE attempts SET ended_at=?,outcome=?,error=? WHERE token=?",
                (now, state, error, token),
            )

    def cancel(self, job_id, actor):
        now = time.time()
        with self.transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise ValueError("unknown job")
            if row["state"] in ("COMPLETED", "FAILED_FINAL", "CANCELLED"):
                raise ValueError("job already terminal")
            db.execute(
                "UPDATE attempts SET ended_at=?,outcome='CANCELLED' WHERE token=? AND ended_at IS NULL",
                (now, row["lease_token"]),
            )
            db.execute(
                "UPDATE jobs SET state='CANCELLED',lease_token=NULL,lease_until=NULL,error='OPERATOR_CANCELLED',updated_at=? WHERE job_id=?",
                (now, job_id),
            )
            self._audit(db, actor, "cancel_job", {"job_id": job_id})

    def complete_experiment(
        self, contract, spec, result, artifact_hash, job_id=None, token=None, resources=None
    ):
        # Internal deterministic worker interface. No public metric-write route.
        if contract.strategy_hash != spec.strategy_hash:
            raise ValueError("strategy mismatch")
        self.register_strategy(spec)
        if fingerprint(result) != artifact_hash:
            raise ValueError("worker result checksum mismatch")
        if result.get("integrity_errors"):
            raise ValueError("execution integrity errors cannot complete an experiment")
        with self.transaction() as db:
            now = time.time()
            if job_id is not None:
                active = db.execute(
                    "SELECT 1 FROM jobs WHERE job_id=? AND lease_token=? AND state='RUNNING' AND lease_until>?",
                    (job_id, token, now),
                ).fetchone()
                if active is None:
                    raise ValueError("STALE_LEASE")
            existing = db.execute(
                "SELECT contract_json,result_json,artifact_hash FROM experiments WHERE experiment_hash=?",
                (contract.experiment_hash,),
            ).fetchone()
            if existing and tuple(existing) != (
                serialize(contract),
                serialize(result),
                artifact_hash,
            ):
                raise ValueError("immutable experiment completion conflict")
            db.execute(
                "INSERT OR IGNORE INTO experiments VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    contract.experiment_hash,
                    contract.experiment_hash,
                    spec.strategy_hash,
                    spec.instrument,
                    serialize(contract),
                    serialize(result),
                    artifact_hash,
                    "SIMULATED",
                    time.time(),
                ),
            )
            if job_id is not None:
                self._resources(db, token, resources)
                db.execute(
                    "UPDATE jobs SET state='COMPLETED',result=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE job_id=?",
                    (
                        serialize({"run_id": contract.experiment_hash, "resources": resources}),
                        now,
                        job_id,
                    ),
                )
                db.execute(
                    "UPDATE attempts SET ended_at=?,outcome='COMPLETED' WHERE token=?",
                    (now, token),
                )
        return contract.experiment_hash
