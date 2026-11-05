BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS improvement_policies(
 policy_hash TEXT PRIMARY KEY, policy_json TEXT NOT NULL,
 search_protocol_hash TEXT NOT NULL REFERENCES search_protocols, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS improvement_controls(
 policy_hash TEXT PRIMARY KEY REFERENCES improvement_policies, enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS improvement_plans(
 plan_hash TEXT PRIMARY KEY, policy_hash TEXT NOT NULL REFERENCES improvement_policies,
 parent_run_id TEXT NOT NULL REFERENCES experiments, evidence_json TEXT NOT NULL,
 generation_cpu_seconds REAL NOT NULL, created_at REAL NOT NULL,
 UNIQUE(policy_hash,parent_run_id)
);
CREATE TABLE IF NOT EXISTS improvement_edges(
 edge_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL REFERENCES improvement_plans,
 child_strategy_hash TEXT NOT NULL REFERENCES strategy_specs,
 child_experiment_hash TEXT NOT NULL, payload_json TEXT NOT NULL,
 hypothesis TEXT NOT NULL, changed_fields_json TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(plan_hash,child_experiment_hash)
);
CREATE TABLE IF NOT EXISTS improvement_outcomes(
 edge_id TEXT PRIMARY KEY REFERENCES improvement_edges,
 status TEXT NOT NULL CHECK(status IN ('TRAIN_IMPROVED_ONLY','TRAIN_NOT_IMPROVED','INCONCLUSIVE','FAILED_CHECKS')),
 evidence_json TEXT NOT NULL, cpu_seconds REAL NOT NULL, created_at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS improvement_policy_no_update BEFORE UPDATE ON improvement_policies
 BEGIN SELECT RAISE(ABORT,'immutable improvement policy'); END;
CREATE TRIGGER IF NOT EXISTS improvement_policy_no_delete BEFORE DELETE ON improvement_policies
 BEGIN SELECT RAISE(ABORT,'immutable improvement policy'); END;
CREATE TRIGGER IF NOT EXISTS improvement_plan_no_update BEFORE UPDATE ON improvement_plans
 BEGIN SELECT RAISE(ABORT,'immutable improvement plan'); END;
CREATE TRIGGER IF NOT EXISTS improvement_plan_no_delete BEFORE DELETE ON improvement_plans
 BEGIN SELECT RAISE(ABORT,'immutable improvement plan'); END;
CREATE TRIGGER IF NOT EXISTS improvement_edge_no_update BEFORE UPDATE ON improvement_edges
 BEGIN SELECT RAISE(ABORT,'immutable improvement edge'); END;
CREATE TRIGGER IF NOT EXISTS improvement_edge_no_delete BEFORE DELETE ON improvement_edges
 BEGIN SELECT RAISE(ABORT,'immutable improvement edge'); END;
CREATE TRIGGER IF NOT EXISTS improvement_outcome_no_update BEFORE UPDATE ON improvement_outcomes
 BEGIN SELECT RAISE(ABORT,'immutable improvement outcome'); END;
CREATE TRIGGER IF NOT EXISTS improvement_outcome_no_delete BEFORE DELETE ON improvement_outcomes
 BEGIN SELECT RAISE(ABORT,'immutable improvement outcome'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(4);
COMMIT;
