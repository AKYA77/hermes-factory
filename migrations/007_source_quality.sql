BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS source_quality_receipts(
 run_id TEXT PRIMARY KEY, inputs_json TEXT NOT NULL, report_json TEXT NOT NULL,
 report_sha256 TEXT NOT NULL, events_sha256 TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS source_quality_attempts(
 attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, outcome TEXT NOT NULL,
 rows_scanned INTEGER NOT NULL, artifact_directory TEXT NOT NULL,
 error TEXT, resources_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS quality_receipt_no_update BEFORE UPDATE ON source_quality_receipts
 BEGIN SELECT RAISE(ABORT,'immutable source quality receipt'); END;
CREATE TRIGGER IF NOT EXISTS quality_receipt_no_delete BEFORE DELETE ON source_quality_receipts
 BEGIN SELECT RAISE(ABORT,'immutable source quality receipt'); END;
CREATE TRIGGER IF NOT EXISTS quality_attempt_no_update BEFORE UPDATE ON source_quality_attempts
 BEGIN SELECT RAISE(ABORT,'immutable source quality attempt'); END;
CREATE TRIGGER IF NOT EXISTS quality_attempt_no_delete BEFORE DELETE ON source_quality_attempts
 BEGIN SELECT RAISE(ABORT,'immutable source quality attempt'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(7);
COMMIT;
