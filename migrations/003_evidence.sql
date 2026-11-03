BEGIN IMMEDIATE;
CREATE TRIGGER IF NOT EXISTS immutable_strategies_delete BEFORE DELETE ON strategy_specs
 BEGIN SELECT RAISE(ABORT,'immutable strategy'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(3);
COMMIT;
