# C2 increment: free HistData ASCII tick pilot

Status: real structural data pilot, not historical strategy or market-quality validation.

The owner's constraint is free sources only. The public HistData.com download
page offers ASCII tick CSV for backtesting, and its FAQ explicitly identifies
bid/ask fields, unavailable volumes and fixed EST without DST. Ordinary free web
form downloads succeeded for EURUSD and XAUUSD January 2025. No FTP purchase,
AWS requester-pays request, registration, paid inference or billing was used.

Retain original ZIP bytes (including provider copyright/gap notices), SHA256,
source URLs, requested instrument/period, retrieval time and source parser policy
outside Git. Source data redistribution is not asserted or performed. Cached
archives must match their requested identity, declared file name and checksum.
No anonymous form token is saved in a manifest or printed by the checked-in client.

The parser uses exact decimal-to-integer conversion, a 1,000,000 source scale,
integer UTC epoch construction at actual millisecond precision, and original row
order for timestamp ties. Source timezone is UTC-05:00 year-round, not US/Eastern
with daylight saving. The volume placeholder is not invented market volume.
Observed whole-file quote grids are EURUSD 0.00001 and XAUUSD 0.001. These are
empirical source observations, not verified broker tick/pip/contract/margin rules;
Gold money calculations remain UNKNOWN_SPEC.

StreamingCatalog keeps at most 8,192 rows per write/readback batch, uses Parquet
ZSTD, rehashes every decoded value and metadata field, preserves duplicates, and
commits a content-addressed directory only after raw/Parquet readback checks.
Invalid ordering, precision or spreads preserve failed output/source references
without a committed manifest. ZIP size/expansion/member/row caps and HTTPS-only
provider redirects bound the importer. No full-month Python list or DataFrame is
built. Existing Catalog readers remain compatible with the canonical schema.

The real pilots structurally verify 2,283,239 EURUSD and 5,798,226 XAUUSD rows.
Gaps over 60 seconds are retained as unclassified evidence (201 and 26 intervals),
not interpolated or silently accepted as market closures. Provider-calendar/gap
review, verified instrument profiles, correction reconciliation, complete 2025/
2026 coverage, data API linkage and historical evaluation remain C2/C3/C6 work.
