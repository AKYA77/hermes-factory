BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS source_observations(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, observation_id TEXT NOT NULL UNIQUE,
 slot_hash TEXT NOT NULL, dataset_hash TEXT NOT NULL, body_json TEXT NOT NULL,
 created_at REAL NOT NULL, UNIQUE(slot_hash,dataset_hash)
);
CREATE TABLE IF NOT EXISTS source_selections(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, selection_id TEXT NOT NULL UNIQUE,
 slot_hash TEXT NOT NULL, observation_id TEXT NOT NULL REFERENCES source_observations(observation_id),
 body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS source_quarantines(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, quarantine_id TEXT NOT NULL UNIQUE,
 observation_id TEXT NOT NULL REFERENCES source_observations(observation_id),
 body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS source_quarantine_resolutions(
 quarantine_id TEXT PRIMARY KEY REFERENCES source_quarantines(quarantine_id),
 body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS source_resolution_no_update BEFORE UPDATE ON source_quarantine_resolutions
 BEGIN SELECT RAISE(ABORT,'immutable source resolution'); END;
CREATE TRIGGER IF NOT EXISTS source_resolution_no_delete BEFORE DELETE ON source_quarantine_resolutions
 BEGIN SELECT RAISE(ABORT,'immutable source resolution'); END;
CREATE INDEX IF NOT EXISTS source_slot_observations ON source_observations(slot_hash,sequence);
CREATE INDEX IF NOT EXISTS source_slot_selections ON source_selections(slot_hash,sequence);
CREATE TRIGGER IF NOT EXISTS source_observation_no_update BEFORE UPDATE ON source_observations
 BEGIN SELECT RAISE(ABORT,'immutable source observation'); END;
CREATE TRIGGER IF NOT EXISTS source_observation_no_delete BEFORE DELETE ON source_observations
 BEGIN SELECT RAISE(ABORT,'immutable source observation'); END;
CREATE TRIGGER IF NOT EXISTS source_selection_no_update BEFORE UPDATE ON source_selections
 BEGIN SELECT RAISE(ABORT,'immutable source selection'); END;
CREATE TRIGGER IF NOT EXISTS source_selection_no_delete BEFORE DELETE ON source_selections
 BEGIN SELECT RAISE(ABORT,'immutable source selection'); END;
CREATE TRIGGER IF NOT EXISTS source_quarantine_no_update BEFORE UPDATE ON source_quarantines
 BEGIN SELECT RAISE(ABORT,'immutable source quarantine'); END;
CREATE TRIGGER IF NOT EXISTS source_quarantine_no_delete BEFORE DELETE ON source_quarantines
 BEGIN SELECT RAISE(ABORT,'immutable source quarantine'); END;
CREATE TABLE IF NOT EXISTS source_comparisons(
 comparison_id TEXT PRIMARY KEY, inputs_json TEXT NOT NULL, report_json TEXT NOT NULL,
 report_sha256 TEXT NOT NULL, events_sha256 TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS source_comparison_no_update BEFORE UPDATE ON source_comparisons
 BEGIN SELECT RAISE(ABORT,'immutable source comparison'); END;
CREATE TRIGGER IF NOT EXISTS source_comparison_no_delete BEFORE DELETE ON source_comparisons
 BEGIN SELECT RAISE(ABORT,'immutable source comparison'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(9);
COMMIT;
