# Schema map

Pydantic source: factory/contracts and factory/config. Generated JSON Schema files
are under schemas/. OpenAPI describes only routes actually implemented.
SQLite forward schema is migrations/001_initial.sql, packaged into the wheel.
Schema version 1 currently has no previous-version migration/restore fixture;
production migration acceptance remains pending.

Fingerprints: strategy effective definition + semantic version; experiment includes
strategy, dataset, profile, engine/fill/code/evaluation versions, windows, seed and
risk. Parent metadata is stored separately and does not change effective semantics.
