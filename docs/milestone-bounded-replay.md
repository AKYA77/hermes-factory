# Completion directive: bounded replay increment

Status **NOT_READY**. Exact source `39e52bb6ee3cea72eceece48d5b81bf058381862`.
See milestone-report.json for hashes, commands, scope and raw measured values.
The preceding accounting/data report is retained under reports/checkpoints/.

The directive was read completely and compared against its reviewed commit.
Existing contracts, v2 ledger, importer, engine, queue, API and dashboard remain.
Completed components were removed from the active implementation backlog, with
remaining acceptance work retained in completion-backlog.md.

Changes: rolling bars and monotonic MTF alignment; bar feature identity independent
of strategy stop/risk; bounded Parquet range reads; single native chunk iterator;
32-byte/quote transient spool; compact diagnostic summaries with reconstructable
canonical references; independent cash/native fill/inventory/account checks.
No matching engine or external ZIP/package was added. See ADR 0008 for limits.

Verification actually run on this source:

- `bash scripts/verify.sh`: 115 passed, zero failed/errors/skipped; Ruff and
  dashboard typecheck/build pass. 146 upstream warnings retained.
- Native delivery equals the materialized native reference for batches of
  1/2/3/8192, including timestamp ties, partial fills, gaps and timeout boundaries.
- Compact summaries match inline diagnostics; canonical offsets reproduce paths.
- 1,000 unique synthetic strategy campaign: 480,000 events, no assertion failures;
  163.615s wall, 138.355 batch-worker CPU seconds, 301,109,248-byte worker peak RSS.
  CPU excludes parent setup/verification; short synthetic fixtures are not historical
  strategy throughput. Authenticated API checks read all 1,000; validated boards empty.
- Real HistData quote delivery with no orders: January EURUSD 2,283,239 rows in
  37.178s wall/37.346 CPU seconds, 329,035,776-byte process RSS; Gold 5,798,226 rows
  in 94.739s/94.924 CPU seconds, 374,054,912-byte process RSS. This tests native feed
  plumbing, not monetary profiles, strategy performance or independent validation.
- Repeated 200,000-EURUSD comparison: exact result hashes match; native materialized
  3.859s wall/4.032 CPU/360,071,168-byte RSS vs streaming 4.079s/4.269 CPU/
  330,231,808-byte RSS. Streaming is adopted for bounded memory; this repeat is
  slower, and no blanket speedup is claimed. OS cache uncontrolled; not a cold run.
- Earlier 200,000-quote feature compilation compares exactly (1,164 signals/hash).
  Initial before/after 2.694s/2.444s and 337,731,584/218,660,864-byte RSS are single
  samples. Final reader/thread configuration further changes resources; do not
  attribute its entire RSS improvement to rolling aggregates alone.
- Baseline historical hashes and isolated 1,016-file/1,000-experiment restore pass.

Commands to reproduce feed/feature probes (source data remains outside Git):

```
.venv/bin/python -m factory.operations.feed_probe --help
.venv/bin/python -m factory.operations.feature_probe --help
.venv/bin/python -m factory.operations.campaign --state .local/new-campaign --count 1000 --batch-size 25
.venv/bin/python -m factory.operations.campaign_api .local/new-campaign
```

Fresh Python/npm audits still fail, upstream compatible pins unchanged. Native
USD Money rounding differs from exact Decimal equity and is explicitly reported;
full monetary evaluation is blocked. Finite L1 exact-cost mismatch remains rejected.
Full calendars/profiles/source coverage, autonomous laboratory/validation/UI/ops
and actual 4-vCPU/8-GB Ubuntu stress/multi-day soak remain unfinished. The measured
host has a four-CPU quota and 32 GiB memory allowance. No production tag exists.
