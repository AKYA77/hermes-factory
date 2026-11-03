# Research interfaces at the amendment checkpoint

All results are historical/paper research. No broker execution lane exists.
Current readiness remains NOT_READY; these are tested development interfaces.

## Canonical inputs and exact features

`Catalog.compose([leaf_hash, ...])` / `catalog-compose HASH...` creates a flat
immutable `data/view-v1` in the state's catalog. Inputs must be in chronological
order for one instrument/provider/scale/precision, without overlapping revisions.
Located quotes retain the original Quote plus partition hash and physical global
sequence. Equal-time partition boundary rows survive. Half-open reads preserve
physical indices. `canonical-view-path/v1` reconstructs exact native paths from
these references. Leaf `data/v1`/`data/v2` IDs and original bytes remain unchanged.

`BarCache.events(catalog, dataset, instrument_hash, code_revision, timeframes,
start_ns=..., end_ns=...)` is a context manager. Consume the event iterator inside
that context. It verifies source/cache bytes, builds missing timeframes in one
pass, and feeds `iter_bar_signals`, the reference interpreter. Budgets fail
explicitly. Cache files are disposable; artifacts, quotes and experiment ledgers
are authoritative. See ADR 0011 for dimensions, caps and crash semantics.

## Research and Tier 0

Register immutable search/v2 with `POST /api/v1/research/protocols` or
`research-register FILE.json`. Search/v1 remains readable with its original ID.
Only explicitly authorized synthetic USD-quote training regions are currently
executable; real monetary/profile/calendar gates remain unresolved. Registration
does not resume paused research. Status, protocols and trials are readable under
`/api/v1/research/{status,protocols,trials}`; operator can disable a region.

Recurring jobs carry `search_trial_id` and the fixed exact-zero screening policy.
Worker returns either a verified native artifact/result, or SCREENED_OUT with a
typed `tier0/v1` receipt and artifact SHA256. A completed screened job has no
experiments row or numeric objective. Only actual verified native training
artifacts supply optimizer objectives. A hash-selected rejected cohort runs the
full native engine; contradictions are quarantined. Status distinguishes screen
counts, native audits and failed-job contradictions. See ADR 0012.

## Controlled improvement

Register `improvement/v1` using `POST /api/v1/improvement/policies` or
`improvement-register FILE.json`. Required field: `search_protocol_hash` for an
existing region. Optional frozen bounds: max_parent_plans (default 8, max 32),
max_children (default/max 4), cpu_budget_seconds (default 300),
min_comparison_trades (default/min 50), max_trade_count_reduction (default/max .5),
reserve_fraction_of_search_cpu (default/max .25). These are training-only plans.

`GET /api/v1/improvement/status` returns persisted policies/counts/resources.
`GET .../plans` and `GET .../children` support limit 1..200 and offset. Child rows
include hypotheses, changed fields and paired evidence. Enable/status/disable are
available in the dashboard; `POST .../policies/HASH/disable` or
`improvement-disable HASH` stops admission. Existing queued work has explicit
job cancellation controls. Global pause prevents admission.

One bounded round retains every parent, hypothesis and child. CPU reservation and
single-job admission limit expansion; unexecuted edges remain pending at budget
limits. Feedback compares entire trade sets on identical non-strategy contracts.
Outcomes are TRAIN_IMPROVED_ONLY, TRAIN_NOT_IMPROVED, INCONCLUSIVE or FAILED_CHECKS.
None grants validation. Open/censored paths, small samples and excessive trade
suppression block training-improvement claims. Existing strategy IDs can have
multiple parent experiment edges. See ADR 0013 and migration 004.

All reads require bearer viewer/operator auth; registration/disable/cancel require
operator. No endpoint accepts supplied performance metrics. Tokens stay in memory
in the browser and are never included in artifacts or reports.

## Local browser rehearsal

The repository adds no production browser dependency. This environment has
Playwright 1.62.1 and Chromium 154.0.8037.57. With those QA prerequisites and a
built dashboard, create a fresh paused fixture:

```
.venv/bin/python scripts/dashboard-fixture.py --state .local/dashboard-qa
.venv/bin/python -m factory.cli --state .local/dashboard-qa serve --port 8097
# in another terminal
node scripts/dashboard-smoke.cjs
```

`FACTORY_BROWSER_STATE` selects another fresh fixture;
`FACTORY_BROWSER_URL` permits loopback only. The test uses real API operations on
that synthetic state, writes screenshots/report under reports/runtime, and
preserves the token in a mode-0600 local file. It does not start research. The
browser regression exposed a blank page caused by a CSP/bootstrap mismatch;
Svelte emits exact hashes and the API verifies them, retaining restrictive script
policy. Rebuild dashboard and restart API together after UI updates.
