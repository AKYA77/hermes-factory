# Completed increments: C3 accounting and C2 structural source pilot

Overall status **NOT_READY**. These are completed, bounded increments within C2/C3,
not full completion of either milestone or the C0–C9/T01–T30 release contract.
Machine-readable source/test/data/resource evidence is in ../milestone-report.json.

The existing API, SvelteKit app, SQLite queue, strategy compiler, Nautilus engine,
risk/spread/target defaults and prior immutable result history are retained.

## C3 accounting increment

The order-aware ledger uses actual Nautilus order/trade IDs, ordered execution
fills, executed quantities, cash/fees, partial entry/exit weighted prices and
terminal states. It does not implement matching. Native fixtures exercise partial
GTC fills, IOC remainder cancellation, a cancellation race, protective cancellation
and safety closure, stop/limit/time exits and tied timestamps. Per-fill basis and
original source row indices make excursions traceable without future fill prices.
Only actual stop-order exits receive stop-loss diagnostic tags.

Intended 1:3 price distances, $20 initial equity, 10% modeled risk, two-pip effective
spread floor and two adverse pips per eligible fill remain fixed. Native fixed-rate
margin now agrees with the instrument profile instead of dividing by leverage a
second time. Requested risk and modeled risk of the actually filled quantity are
separate. Limits are checked, and engine rejections, unexpected fees and exact-price
mismatches cannot become official successful worker results.

Execution context is adverse-fill/v2 plus actual Git/content source identity.
Old v1 execution requests are read-only; v1 history is preserved in an explicit
legacy board view and is not mixed into the default v2 board. A caller cannot
claim an invented source commit. Pending older-source jobs must not be silently
run under new code. This does not defend against a malicious trusted local writer
or in-process code execution; production release/signature validation is unfinished.

A deliberately exhausted L1 fixture reveals Nautilus's extra-tick remainder
behavior. Its actual fills are accounted, but the pricing mismatch is reported
and rejected for the exact-cost contract. No engine fork or result-price rewrite
hides the limitation. Thus full finite-liquidity C3 acceptance remains open.

## C2 real-data structural increment

Ordinary free HistData ASCII web downloads succeeded for January 2025:

| Instrument | Real source quotes | Observed quote grid | Import/readback batch |
|---|---:|---:|---:|
| EURUSD | 2,283,239 | 0.00001 | 8,192 rows |
| XAUUSD | 5,798,226 | 0.001 | 8,192 rows |

Original ZIPs include provider notices and gap reports and remain outside Git.
Source checksums, instrument/period file identity, exact decimal integer scaling,
fixed UTC-05:00 (no DST) -> UTC and actual millisecond source precision are retained.
Parquet/ZSTD is read back in bounded batches; every quote's values, original order
and metadata are hashed and verified before atomic manifest publication. No full
month list/DataFrame, resampling, smoothing, price rounding, invented volumes or
synthesized ticks are used. Invalid partitions never get a committed manifest.

These are structural checks. There are 201/26 >60-second gaps requiring calendar
review; they are not silently classified as valid market closures. The empirical
Gold grid does not define a universal trading pip, contract size, tick value or
volume/margin profile. No historical strategy performance, final holdout, validated
leaderboard or 2026 coverage is claimed. The owner confirmed Factory.pdf is the original blueprint under the other filename.
Its detailed §§8.5/9.1 supply the cost/risk formulas, and §16 supplies acceptance gates.

Pilot defaults deliberately use a separate .local/historical-catalog. The existing
Catalog reader can consume the same schema; approved active-state ingestion later
uses --catalog <state>/catalog. Importing data does not itself authorize evaluation.

```
.venv/bin/python -m factory.operations.import_history --instrument EURUSD --year 2025 --month 1
.venv/bin/python -m factory.operations.import_history --instrument XAUUSD --year 2025 --month 1
.venv/bin/python -m factory.operations.import_benchmark --instrument EURUSD --year 2025 --month 1
.venv/bin/python -m factory.operations.import_benchmark --instrument XAUUSD --year 2025 --month 1
```

Downloads are capped at 128 MiB, archive expansion at 512 MiB, rows at 4 KiB and
batches at 65,536 rows (8,192 default). Unsupported redirects, precision, units,
source ordering and corrupted cached archives fail explicitly. Re-imports preserve
content identities. These caps do not complete operational disk quotas or recovery.

## Verification and outstanding gates

The report lists exact commands/exit codes, test counts, source commit/hash, real
import resources and a separate synthetic v2 campaign/fixture replay measurement.
Real import measurements describe ingestion/storage only. Short synthetic replay
measurements are correctness regressions, not production strategy throughput.
The host has a four-CPU cgroup quota and 32 GiB memory allowance; it is not the
requested Ubuntu Contabo 8-GB VPS, and no VPS soak/reboot/release gate is passed.

Security assessments are in ADR 0007. Fresh Python/npm scans remain failing on
fsspec/deepmerge; no checks or findings are suppressed. Instrument/calendar/reference gates, complete autonomous research, OOS/WFO and
robustness, full UI/controls, target deployment/recovery and release remain open.
See ../known-limitations.md and implementation-plan.md. No production tag exists.
