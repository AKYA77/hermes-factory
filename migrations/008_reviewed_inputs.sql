BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS reviewed_inputs(
 review_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
 body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS input_revocations(
 review_id TEXT PRIMARY KEY REFERENCES reviewed_inputs(review_id),
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS reviewed_input_no_update BEFORE UPDATE ON reviewed_inputs
 BEGIN SELECT RAISE(ABORT,'immutable reviewed input'); END;
CREATE TRIGGER IF NOT EXISTS reviewed_input_no_delete BEFORE DELETE ON reviewed_inputs
 BEGIN SELECT RAISE(ABORT,'immutable reviewed input'); END;
CREATE TRIGGER IF NOT EXISTS input_revocation_no_update BEFORE UPDATE ON input_revocations
 BEGIN SELECT RAISE(ABORT,'immutable input revocation'); END;
CREATE TRIGGER IF NOT EXISTS input_revocation_no_delete BEFORE DELETE ON input_revocations
 BEGIN SELECT RAISE(ABORT,'immutable input revocation'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(8);
COMMIT;
