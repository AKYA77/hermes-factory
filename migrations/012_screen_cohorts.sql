BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS screen_cohorts(
 cohort_id TEXT PRIMARY KEY, body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS screen_cohort_members(
 cohort_id TEXT NOT NULL REFERENCES screen_cohorts,
 experiment_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('calibration','prospective')),
 job_id TEXT REFERENCES jobs, selected INTEGER NOT NULL CHECK(selected IN (0,1)),
 PRIMARY KEY(cohort_id,experiment_hash)
);
CREATE TABLE IF NOT EXISTS screen_cohort_effective_inputs(
 effective_hash TEXT PRIMARY KEY, cohort_id TEXT NOT NULL REFERENCES screen_cohorts,
 experiment_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS screen_effective_no_update BEFORE UPDATE ON screen_cohort_effective_inputs
 BEGIN SELECT RAISE(ABORT,'immutable screen effective input'); END;
CREATE TRIGGER IF NOT EXISTS screen_effective_no_delete BEFORE DELETE ON screen_cohort_effective_inputs
 BEGIN SELECT RAISE(ABORT,'immutable screen effective input'); END;
CREATE UNIQUE INDEX IF NOT EXISTS independent_screen_cohort_member
 ON screen_cohort_members(experiment_hash) WHERE role='prospective';
CREATE TRIGGER IF NOT EXISTS screen_cohort_no_update BEFORE UPDATE ON screen_cohorts
 BEGIN SELECT RAISE(ABORT,'immutable screen cohort'); END;
CREATE TRIGGER IF NOT EXISTS screen_cohort_no_delete BEFORE DELETE ON screen_cohorts
 BEGIN SELECT RAISE(ABORT,'immutable screen cohort'); END;
CREATE TRIGGER IF NOT EXISTS screen_member_no_update BEFORE UPDATE ON screen_cohort_members
 BEGIN SELECT RAISE(ABORT,'immutable screen cohort member'); END;
CREATE TRIGGER IF NOT EXISTS screen_member_no_delete BEFORE DELETE ON screen_cohort_members
 BEGIN SELECT RAISE(ABORT,'immutable screen cohort member'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(12);
COMMIT;
