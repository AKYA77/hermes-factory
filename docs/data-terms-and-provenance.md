# Data terms and provenance

No historical data has been downloaded. The proposed Dukascopy historical terms
page and datafeed endpoint returned proxy tunnel 403s. Network additions are saved
in the environment draft, not applied by that save. Required additions:
www.dukascopy.com, datafeed.dukascopy.com; GitHub management needs api.github.com.

The dukascopy-node upstream source license was read (MIT); this does not license
underlying provider market data. Its permanent importer integration awaits actual
provider usage terms/access review. Do not infer legal permission from a library
license or a public endpoint. No broker login or execution adapter exists.

All current quotes are project-generated synthetic fixtures. Raw synthetic bytes,
precision, scale, source, record order, checksums and manifest are saved. They
provide no evidence of strategy performance in 2025/2026 markets. Test profile
Gold pip and volume conventions are deliberately synthetic and must never be
promoted into production metadata. UNKNOWN_SPEC blocks real monetary calculations.

Pending: actual one-day/week Forex and Gold pilot, source limits, legal decision,
calendar-aware gaps, DST fixtures, latest verified 2026 endpoint per instrument,
bounded batch importer, incremental reconciliation, immutable source revisions,
2025/2026 backfill, storage forecasts and off-host encrypted backups.
