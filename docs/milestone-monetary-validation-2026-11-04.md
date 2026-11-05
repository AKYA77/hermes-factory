# Monetary correctness and connected validation evidence — 4 November 2026

Status: **IMPLEMENTING / NOT_READY**. This completes a tested implementation
increment, not C3, C6, C7, SOFTWARE_VERIFIED or the full owner mandate.

Scientific code: `6ea90a76d5ab9d4f314e782abdfc552dbe64e744`, source SHA256
`459870a2b663551360b9e625ed1d2038c5e15d944b0f87d3e3defd6379801922`.
Evidence: [hashed manifest](../reports/milestones/2026-11-04-monetary-validation/manifest.json).
All 1,000 campaign artifacts contain that same runtime provenance. Frontend
source hashes are recorded separately in the browser evidence. Existing reports
remain preserved; earlier measurements are not relabeled as new-source results.

Implemented changes are detailed in ADRs 0016–0018: explicit IOC exhausted-market
remainders, independent native account/position rounding references, same-source
ordered conversion context, profile lots to native base units, exact risk/margin
step feasibility, rational account-sum receipts and dated marked equity. Native
matching, $20/10%, intended 3R and declared conservative costs remain intact.
The repeating-rate boundary regression previously admitted 10000 units slightly
above $2 modeled loss; it now selects the legal lower 9999.999 units.

The connected Validation Lab registers prospective protocols with visible
criteria, shows actual staged jobs/forward metrics/annual and pooled scenarios,
plots observed marked-equity envelopes, shows protected-window state and disables
new stages. JSON API downloads preserve original response bytes; new UTC
boundaries are sent as exact nanosecond strings, avoiding browser-number loss.
The generic inspector is explicitly display-only. Full forensic dashboards,
cohort diagnostics, exports/PDF and the remaining product workflows are unfinished.

## Actual verification

- `bash scripts/verify.sh`: 259 passed, no failures/skips, 322 recorded third-party
  warnings, 71.96 seconds; Ruff and dashboard check/build passed.
- All-eight synthetic native long/short stop/target, 0.001 Gold grid, lot/base-unit
  equivalence, FX timestamp ties/chunk/materialized parity, open marks, gap
  insolvency, independent quote/account Money and exact-risk boundary fixtures pass.
- Actual supervised USDJPY training plus immutable protected confirmation pass.
- Latest frontend check/build: zero Svelte errors/warnings. API/CSP regression:
  8 passed, two third-party warnings, 1.85 seconds.
- Chromium 154.0.8037.57: prospective registration, exact fractional-millisecond
  boundary/export, preserved pause, protected status, protocol stop, actual report,
  forward curve and annual/pooled tables pass. Desktop and 390-pixel mobile runs
  have no page errors or document overflow. Existing research/improvement/job
  cancellation browser regression also passes.
- The browser-registered synthetic reference completed 19 actual native jobs
  (five training experiments, fourteen evaluations), 20 coordinator cycles,
  37.74 seconds. Result is **INSUFFICIENT_EVIDENCE**: forward counts 28 and 1;
  final count 23. No historical validation or promotion is claimed.
- All original-source and Parquet bytes for the eight January historical
  partitions were rehashed; manifest/schema/count/bounds checks pass for
  21,345,746 preserved rows. This was not a new full-row semantic scan or a
  historical strategy backtest. Calendar/profile acceptance remains open.

## Measured resources

| Workload | Wall seconds | CPU seconds | Memory evidence |
|---|---:|---:|---|
| Eight isolated supervised synthetic native jobs, 100,000 quotes each | 100.01 total; 70.37 workers | 100.69 parent + children; 68.19 workers | Reported process/worker high-water 371.996 MiB; sampled worker maximum 315.340 MiB |
| 1,000 distinct synthetic strategies, 480 quotes each, four USD-quote pairs | 197.46 | 166.90 batch children | Peak worker 288.277 MiB |

The eight-instrument run delivered 800,000 source quotes and 1,100,000 actual
native quote events (three explicit conversion-context feeds), with 2,664 closed
trades, open final inventory preserved and no integrity errors. Preparation took
29.64 seconds; state occupied 42,448,857 bytes. Per-process high-water accounting
may retain a larger pre-exec/fork high-water; sampled RSS is separately recorded.
These are not simultaneous system RSS, a forced-8GB test or historical throughput.
The host quota is four CPUs with a 32-GiB cgroup limit, not the Contabo target.

The 1,000 campaign completed all jobs, 14,620 trades and 480,000 source events;
568 replays retained open end-of-sample positions. There are no campaign assertion
failures. Its small batched harness amortizes imports and does not demonstrate
production tick-history throughput, profitability, billions of backtests or soak
reliability.

Reproduce on the appropriate exact source checkout, with new isolated state:

```sh
.venv/bin/python scripts/benchmark-monetary.py --state .local/new-money-probe --rows 100000 --output reports/runtime/new-money-probe.json
.venv/bin/python -m factory.operations.campaign --state .local/new-campaign --count 1000 --batch-size 25
.venv/bin/python scripts/validation-browser-fixture.py --state .local/new-validation-ui
.venv/bin/python -m factory.cli --state .local/new-validation-ui serve --port 8101
FACTORY_BROWSER_STATE=.local/new-validation-ui FACTORY_BROWSER_URL=http://127.0.0.1:8101 node scripts/validation-browser-smoke.cjs
```

The browser script mutates only its isolated test state and disables its new
protocol after checking registration. Keep the coordinator stopped for that
registration rehearsal. A completed-report inspection uses `--inspect-existing`
on state with an actual native report; it never inserts pretend report metrics.

## Failed checks and remaining work

Fresh dependency gates still exit 1: PYSEC-2026-4217 in fsspec2026.2.0
(Nautilus's exact pin; fix >=2026.6.0), plus four low-severity npm findings in the
deepmerge chain. No excludes, overrides, downgraded gates or audit suppressions.
ADR 0007 remains applicable. A limited reachable-history signature scan checked
459 blobs / 4,933,863 bytes without known-token/private-key matches; this is not
a guarantee of absence or an online credential validation.

Mandatory unfinished work includes verified dated profiles/calendar/revisions;
approximate cost-aware screening and calibrated audits; shared indicator outputs;
all required families/continuous discovery/recursive diagnostics; robust global
scientific decisions and comparable validated rankings; full dashboard/lifecycle/
installer/backup/update/rollback/handoff; installed provenance; and target-host
installation/stress/soak. In particular the current synthetic protocol still
consumes confirmation even after weak OOS evidence, and its decision needs full
marked-equity/data-completeness admission. These are active scientific-correctness
items, not waived requirements or accepted historical behavior.

All three readiness states stay false. No release tag, production claim, real
money execution or new push has occurred. Repository visibility remains PUBLIC
as last observed; owner decision is pending under mandate section 13, so new
pushes remain held. Last remote branch commit remains `9034cbc`.
