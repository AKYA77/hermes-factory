PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_migrations VALUES(1);
CREATE TABLE IF NOT EXISTS strategy_specs(
 strategy_id TEXT PRIMARY KEY, spec_json TEXT NOT NULL, parent_id TEXT REFERENCES strategy_specs,
 hypothesis TEXT, changed_fields TEXT NOT NULL DEFAULT '[]', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments(
 run_id TEXT PRIMARY KEY, experiment_hash TEXT NOT NULL UNIQUE,
 strategy_id TEXT NOT NULL REFERENCES strategy_specs, instrument TEXT NOT NULL,
 contract_json TEXT NOT NULL, result_json TEXT NOT NULL, artifact_hash TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('SIMULATED','INSUFFICIENT_EVIDENCE','FAILED_CHECKS','VALIDATED')),
 created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS immutable_experiments_update BEFORE UPDATE ON experiments
 BEGIN SELECT RAISE(ABORT,'immutable experiment'); END;
CREATE TRIGGER IF NOT EXISTS immutable_experiments_delete BEFORE DELETE ON experiments
 BEGIN SELECT RAISE(ABORT,'immutable experiment'); END;
CREATE TRIGGER IF NOT EXISTS immutable_strategies_update BEFORE UPDATE ON strategy_specs
 BEGIN SELECT RAISE(ABORT,'immutable strategy'); END;
CREATE TABLE IF NOT EXISTS jobs(
 job_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
 payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'QUEUED'
 CHECK(state IN ('QUEUED','RUNNING','COMPLETED','FAILED_RETRYABLE','FAILED_FINAL','CANCELLED')),
 priority INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
 available_at REAL NOT NULL, lease_until REAL, lease_token TEXT, result TEXT, error TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS job_claim ON jobs(state,available_at,priority);
CREATE TABLE IF NOT EXISTS attempts(
 attempt_id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs,
 token TEXT UNIQUE NOT NULL, started_at REAL NOT NULL, ended_at REAL, outcome TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS audit_events(
 event_id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL,
 payload TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events
 BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
 BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
CREATE TABLE IF NOT EXISTS controls(key TEXT PRIMARY KEY,value TEXT NOT NULL);
INSERT OR IGNORE INTO controls VALUES('paused','true');
CREATE TABLE IF NOT EXISTS research_coverage(
 instrument TEXT NOT NULL, family TEXT NOT NULL, timeframe TEXT NOT NULL,
 cpu_seconds REAL NOT NULL DEFAULT 0, proposals INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(instrument,family,timeframe)
);
CREATE TABLE IF NOT EXISTS holdout_uses(
 contract_hash TEXT NOT NULL, run_id TEXT NOT NULL, consumed_at REAL NOT NULL,
 PRIMARY KEY(contract_hash,run_id)
);
