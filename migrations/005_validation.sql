BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS research_input_uses(
 use_id TEXT PRIMARY KEY, instrument TEXT NOT NULL, evidence_kind TEXT NOT NULL,
 dataset_hash TEXT NOT NULL, start_ns INTEGER NOT NULL, end_ns INTEGER NOT NULL,
 purpose TEXT NOT NULL, owner_id TEXT NOT NULL, created_at REAL NOT NULL,
 CHECK(start_ns<end_ns)
);
CREATE INDEX IF NOT EXISTS input_use_intervals ON research_input_uses(instrument,evidence_kind,start_ns,end_ns);
CREATE TABLE IF NOT EXISTS protected_holdouts(
 holdout_id TEXT PRIMARY KEY, spec_json TEXT NOT NULL, instrument TEXT NOT NULL,
 evidence_kind TEXT NOT NULL, dataset_hash TEXT NOT NULL,
 start_ns INTEGER NOT NULL, end_ns INTEGER NOT NULL, created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS holdout_intervals ON protected_holdouts(instrument,evidence_kind,start_ns,end_ns);
CREATE TABLE IF NOT EXISTS holdout_selections(
 holdout_id TEXT PRIMARY KEY REFERENCES protected_holdouts,
 training_run_id TEXT NOT NULL REFERENCES experiments,
 payload_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS holdout_consumptions(
 holdout_id TEXT PRIMARY KEY REFERENCES holdout_selections,
 authorization_id TEXT UNIQUE NOT NULL, contract_json TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluation_results(
 evaluation_id TEXT PRIMARY KEY, contract_json TEXT NOT NULL,
 result_json TEXT NOT NULL, artifact_hash TEXT NOT NULL,
 holdout_id TEXT REFERENCES protected_holdouts, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS input_use_no_update BEFORE UPDATE ON research_input_uses
 BEGIN SELECT RAISE(ABORT,'immutable input use'); END;
CREATE TRIGGER IF NOT EXISTS input_use_no_delete BEFORE DELETE ON research_input_uses
 BEGIN SELECT RAISE(ABORT,'immutable input use'); END;
CREATE TRIGGER IF NOT EXISTS holdout_no_update BEFORE UPDATE ON protected_holdouts
 BEGIN SELECT RAISE(ABORT,'immutable protected holdout'); END;
CREATE TRIGGER IF NOT EXISTS holdout_no_delete BEFORE DELETE ON protected_holdouts
 BEGIN SELECT RAISE(ABORT,'immutable protected holdout'); END;
CREATE TRIGGER IF NOT EXISTS selection_no_update BEFORE UPDATE ON holdout_selections
 BEGIN SELECT RAISE(ABORT,'immutable holdout selection'); END;
CREATE TRIGGER IF NOT EXISTS selection_no_delete BEFORE DELETE ON holdout_selections
 BEGIN SELECT RAISE(ABORT,'immutable holdout selection'); END;
CREATE TRIGGER IF NOT EXISTS consumption_no_update BEFORE UPDATE ON holdout_consumptions
 BEGIN SELECT RAISE(ABORT,'immutable holdout consumption'); END;
CREATE TRIGGER IF NOT EXISTS consumption_no_delete BEFORE DELETE ON holdout_consumptions
 BEGIN SELECT RAISE(ABORT,'immutable holdout consumption'); END;
CREATE TRIGGER IF NOT EXISTS evaluation_no_update BEFORE UPDATE ON evaluation_results
 BEGIN SELECT RAISE(ABORT,'immutable evaluation result'); END;
CREATE TRIGGER IF NOT EXISTS evaluation_no_delete BEFORE DELETE ON evaluation_results
 BEGIN SELECT RAISE(ABORT,'immutable evaluation result'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(5);
COMMIT;
