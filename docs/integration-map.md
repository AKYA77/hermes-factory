# Current tested integration map

| Producer | Consumer | Contract | Evidence |
|---|---|---|---|
| HTTP proposal | Coordinator queue | Proposal + immutable experiment hash | integration/test_vertical.py |
| Catalog | Worker | verified manifest + canonical integer quotes | integration/test_data.py |
| Shared closed-bar operator | Nautilus adapter | available_at + BUY/SELL | integration/test_vertical.py |
| Nautilus fills/quotes | Diagnostics | entry/exit + executable-side path | simulation/test_engine.py |
| Worker artifact | SQLite writer | checksummed internal result | integration/test_vertical.py |
| SQLite | API/board | instrument-specific immutable run refs | security/test_api.py |
| SQLite/catalog/artifacts | Backup verifier | files + SHA256 manifest | recovery/test_store.py |

No component accepts model-generated metrics through HTTP. GET routes have bounded
pagination where implemented. Bearer auth, viewer/operator roles; no cookie auth.
The complete required blueprint surface is not yet implemented: see acceptance matrix.
