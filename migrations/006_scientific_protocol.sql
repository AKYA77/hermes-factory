BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS validation_protocols(
 protocol_id TEXT PRIMARY KEY, spec_json TEXT NOT NULL,
 holdout_id TEXT NOT NULL REFERENCES protected_holdouts, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS validation_controls(
 protocol_id TEXT PRIMARY KEY REFERENCES validation_protocols, enabled INTEGER NOT NULL DEFAULT 1, last_tick REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS validation_training_regions(
 protocol_id TEXT NOT NULL REFERENCES validation_protocols, fold_index INTEGER NOT NULL,
 search_protocol_hash TEXT NOT NULL REFERENCES search_protocols, created_at REAL NOT NULL,
 PRIMARY KEY(protocol_id,fold_index)
);
CREATE TABLE IF NOT EXISTS validation_stages(
 stage_id TEXT PRIMARY KEY, protocol_id TEXT NOT NULL REFERENCES validation_protocols,
 stage_name TEXT NOT NULL, payload_json TEXT NOT NULL, training_run_id TEXT NOT NULL REFERENCES experiments,
 created_at REAL NOT NULL, UNIQUE(protocol_id,stage_name)
);
CREATE TABLE IF NOT EXISTS retrospective_report_authorizations(
 authorization_id TEXT PRIMARY KEY, holdout_id TEXT NOT NULL REFERENCES holdout_consumptions,
 contract_json TEXT NOT NULL, stage_id TEXT NOT NULL REFERENCES validation_stages,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS validation_protocol_reports(
 protocol_id TEXT PRIMARY KEY REFERENCES validation_protocols, report_json TEXT NOT NULL,
 artifact_hash TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS validation_protocol_no_update BEFORE UPDATE ON validation_protocols
 BEGIN SELECT RAISE(ABORT,'immutable validation protocol'); END;
CREATE TRIGGER IF NOT EXISTS validation_protocol_no_delete BEFORE DELETE ON validation_protocols
 BEGIN SELECT RAISE(ABORT,'immutable validation protocol'); END;
CREATE TRIGGER IF NOT EXISTS validation_region_no_update BEFORE UPDATE ON validation_training_regions
 BEGIN SELECT RAISE(ABORT,'immutable validation training region'); END;
CREATE TRIGGER IF NOT EXISTS validation_region_no_delete BEFORE DELETE ON validation_training_regions
 BEGIN SELECT RAISE(ABORT,'immutable validation training region'); END;
CREATE TRIGGER IF NOT EXISTS validation_stage_no_update BEFORE UPDATE ON validation_stages
 BEGIN SELECT RAISE(ABORT,'immutable validation stage'); END;
CREATE TRIGGER IF NOT EXISTS validation_stage_no_delete BEFORE DELETE ON validation_stages
 BEGIN SELECT RAISE(ABORT,'immutable validation stage'); END;
CREATE TRIGGER IF NOT EXISTS report_authorization_no_update BEFORE UPDATE ON retrospective_report_authorizations
 BEGIN SELECT RAISE(ABORT,'immutable report authorization'); END;
CREATE TRIGGER IF NOT EXISTS report_authorization_no_delete BEFORE DELETE ON retrospective_report_authorizations
 BEGIN SELECT RAISE(ABORT,'immutable report authorization'); END;
CREATE TRIGGER IF NOT EXISTS protocol_report_no_update BEFORE UPDATE ON validation_protocol_reports
 BEGIN SELECT RAISE(ABORT,'immutable validation report'); END;
CREATE TRIGGER IF NOT EXISTS protocol_report_no_delete BEFORE DELETE ON validation_protocol_reports
 BEGIN SELECT RAISE(ABORT,'immutable validation report'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(6);
COMMIT;
