BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS discovery_policies(
 policy_id TEXT PRIMARY KEY, policy_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_controls(
 policy_id TEXT PRIMARY KEY REFERENCES discovery_policies,
 enabled INTEGER NOT NULL, reason TEXT, source_cursor TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS discovery_regions(
 region_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES discovery_policies,
 protocol_hash TEXT NOT NULL UNIQUE, protocol_json TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS discovery_region_controls(
 region_id TEXT PRIMARY KEY REFERENCES discovery_regions,
 state TEXT NOT NULL CHECK(state IN ('PLANNED','REGISTERED','EXHAUSTED','BLOCKED')),
 reason TEXT
);
CREATE TABLE IF NOT EXISTS discovery_source_rejections(
 rejection_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES discovery_policies,
 body_json TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS discovery_rejection_no_update BEFORE UPDATE ON discovery_source_rejections
 BEGIN SELECT RAISE(ABORT,'immutable discovery source rejection'); END;
CREATE TRIGGER IF NOT EXISTS discovery_rejection_no_delete BEFORE DELETE ON discovery_source_rejections
 BEGIN SELECT RAISE(ABORT,'immutable discovery source rejection'); END;
CREATE TRIGGER IF NOT EXISTS discovery_policy_no_update BEFORE UPDATE ON discovery_policies
 BEGIN SELECT RAISE(ABORT,'immutable discovery policy'); END;
CREATE TRIGGER IF NOT EXISTS discovery_policy_no_delete BEFORE DELETE ON discovery_policies
 BEGIN SELECT RAISE(ABORT,'immutable discovery policy'); END;
CREATE TRIGGER IF NOT EXISTS discovery_region_no_update BEFORE UPDATE ON discovery_regions
 BEGIN SELECT RAISE(ABORT,'immutable discovery region'); END;
CREATE TRIGGER IF NOT EXISTS discovery_region_no_delete BEFORE DELETE ON discovery_regions
 BEGIN SELECT RAISE(ABORT,'immutable discovery region'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(11);
COMMIT;
