BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS cost_label_audits(
 experiment_hash TEXT PRIMARY KEY REFERENCES experiments(experiment_hash),
 region_hash TEXT NOT NULL, policy_hash TEXT NOT NULL, body_json TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS cost_label_regions ON cost_label_audits(region_hash);
CREATE TRIGGER IF NOT EXISTS cost_label_audit_no_update BEFORE UPDATE ON cost_label_audits
 BEGIN SELECT RAISE(ABORT,'immutable cost label audit'); END;
CREATE TRIGGER IF NOT EXISTS cost_label_audit_no_delete BEFORE DELETE ON cost_label_audits
 BEGIN SELECT RAISE(ABORT,'immutable cost label audit'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(10);
COMMIT;
