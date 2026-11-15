BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS comparability_contracts(
 contract_hash TEXT PRIMARY KEY, instrument TEXT NOT NULL,
 dataset_hash TEXT NOT NULL, evaluation_start_ns INTEGER NOT NULL,
 evaluation_end_ns INTEGER NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS comparability_contract_peers(
 contract_hash TEXT NOT NULL REFERENCES comparability_contracts,
 peer_hash TEXT NOT NULL,
 PRIMARY KEY(contract_hash,peer_hash)
);
CREATE TRIGGER IF NOT EXISTS comparability_contract_no_update BEFORE UPDATE ON comparability_contracts
 BEGIN SELECT RAISE(ABORT,'immutable comparability contract'); END;
CREATE TRIGGER IF NOT EXISTS comparability_contract_no_delete BEFORE DELETE ON comparability_contracts
 BEGIN SELECT RAISE(ABORT,'immutable comparability contract'); END;
INSERT OR IGNORE INTO schema_migrations VALUES(13);
COMMIT;
