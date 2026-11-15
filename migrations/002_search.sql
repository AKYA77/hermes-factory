BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS search_protocols(
 protocol_hash TEXT PRIMARY KEY, protocol_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS search_controls(
 protocol_hash TEXT PRIMARY KEY REFERENCES search_protocols, enabled INTEGER NOT NULL DEFAULT 1,
 reason TEXT, updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS search_trials(
 trial_id TEXT PRIMARY KEY, protocol_hash TEXT NOT NULL REFERENCES search_protocols,
 trial_number INTEGER NOT NULL, parameters_json TEXT NOT NULL, spec_json TEXT NOT NULL,
 contract_json TEXT NOT NULL, generation_cpu_seconds REAL NOT NULL,
 created_at REAL NOT NULL, UNIQUE(protocol_hash,trial_number)
);
CREATE TABLE IF NOT EXISTS search_outcomes(
 trial_id TEXT PRIMARY KEY REFERENCES search_trials,
 outcome TEXT NOT NULL CHECK(outcome IN ('COMPLETE','PRUNED','FAIL')),
 objective REAL, run_id TEXT REFERENCES experiments, cpu_seconds REAL NOT NULL,
 reason TEXT NOT NULL, created_at REAL NOT NULL,
 CHECK((outcome='COMPLETE' AND objective IS NOT NULL AND run_id IS NOT NULL)
       OR (outcome!='COMPLETE' AND objective IS NULL))
);
CREATE TRIGGER IF NOT EXISTS search_protocol_no_update BEFORE UPDATE ON search_protocols
 BEGIN SELECT RAISE(ABORT,'immutable search protocol'); END;
CREATE TRIGGER IF NOT EXISTS search_protocol_no_delete BEFORE DELETE ON search_protocols
 BEGIN SELECT RAISE(ABORT,'immutable search protocol'); END;
CREATE TRIGGER IF NOT EXISTS search_trial_no_update BEFORE UPDATE ON search_trials
 BEGIN SELECT RAISE(ABORT,'immutable search trial'); END;
CREATE TRIGGER IF NOT EXISTS search_trial_no_delete BEFORE DELETE ON search_trials
 BEGIN SELECT RAISE(ABORT,'immutable search trial'); END;
CREATE TRIGGER IF NOT EXISTS search_outcome_no_update BEFORE UPDATE ON search_outcomes
 BEGIN SELECT RAISE(ABORT,'immutable search outcome'); END;
CREATE TRIGGER IF NOT EXISTS search_outcome_no_delete BEFORE DELETE ON search_outcomes
 BEGIN SELECT RAISE(ABORT,'immutable search outcome'); END;
CREATE TABLE IF NOT EXISTS attempt_resources(
 token TEXT PRIMARY KEY REFERENCES attempts(token), resources_json TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS attempt_resources_no_update BEFORE UPDATE ON attempt_resources
 BEGIN SELECT RAISE(ABORT,'immutable attempt resources'); END;
CREATE TRIGGER IF NOT EXISTS attempt_resources_no_delete BEFORE DELETE ON attempt_resources
 BEGIN SELECT RAISE(ABORT,'immutable attempt resources'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(2);
COMMIT;
