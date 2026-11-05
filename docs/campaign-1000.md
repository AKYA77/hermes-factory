# 1,000-strategy software verification

Status: software checks passed within the scope below; NOT_READY for production.
The authoritative machine-readable evidence is ../campaign-report.json. Earlier
40-test/2,000-quote checkpoint reports are superseded for current code readiness.

The frozen finite grid contains 1,000 unique strategy definitions, with 250 for
each of EURUSD, GBPUSD, AUDUSD and NZDUSD. It covers momentum, mean reversion and
breakout, M1/M5, lookbacks and legal tick-based stop distances. Each receives a
Nautilus engine replay with 480 synthetic minute-spaced quotes, generated from
an eight-hour sine fixture. Four canonical datasets are reused; 480,000 replayed
events are not 480,000 distinct source quotes. No 2025/2026 market data is claimed.

Actual post-fix results:

- 1,000 completed jobs and 1,000 unique engine replays; zero campaign assertion failures.
- 14,620 closed synthetic trades; 424 zero-trade strategies remain recorded.
- 568 runs have an open position at sample end, explicitly censored/flagged.
- Intended 3R distance, projected risk budget, diagnostics count, result/artifact
  hashes and absence of engine rejections checked across completed results.
- Real authenticated loopback API paginated all 1,000 experiments, read diagnostics
  and four top-five boards, rejected anonymous API access and kept validated boards empty.
- Backup/isolated restore verifies 1,016 files and 1,000 jobs/experiments.
- Full regression suite: 45 passed, zero failed/skipped; dashboard check/build passed.

Final campaign measurement: 136.0s wall, 120.0 CPU-seconds, 301,531,136 bytes peak
worker RSS, 40 sequential batches of 25 independent engines. Linux x86_64,
Python 3.12.14, NautilusTrader 1.231.0. Host memory is ~34GB and cgroup quota is
4 CPUs; this is not a forced-8GB Contabo soak. Batching is an explicitly separate
test harness to amortize imports; production still isolates each individual job.
The report records the exact tested source commit, dataset/strategy/experiment
identities, batch measurements, repeated-result agreement and scope limitations.

Reproduce in a fresh state directory:

```
.venv/bin/python -m factory.operations.campaign --state .local/new-campaign --count 1000 --batch-size 25
.venv/bin/python -m factory.operations.campaign_api .local/new-campaign
bash scripts/verify.sh
```

Bugs found and corrected: already-triggered stop submissions caused bracket
sibling rejection; snapshot verification leaked connections and created disappearing
WAL files during restore copies. Synthetic smoke fixtures now use a feasible
six-pip stop, while the campaign retains infeasible two-/four-pip proposals as
explicit skips. Changed campaign plans cannot enqueue extra jobs, and invalid
batch sizes fail before setup. See ADRs 0003 and 0004 and regression tests.

## Free historical data — blocked, not simulated as a success

The owner requires free sources only. The historical page and official source
instructions were accessible, but the tick endpoint returned HTTP 429 with a link
to https://www.dukascopy.com/wiki/en/development/data-export/. That document requires
AWS credentials and Requester Pays billing. No AWS connection or paid authorization
is available; no paid request was made. General site terms and source instructions
were read. No historical tick file was successfully downloaded.

The free-source candidate https://www.histdata.com/download-free-forex-data/ is
blocked by the environment proxy (403). A new network draft adds histdata.com and
www.histdata.com without replacing existing hosts or publishing the environment.
Access, licensing, available bid/ask tick formats, timestamp conventions and quote
precision must be checked after that setting is applied. Do not label uninspected
bars/ticks as verified historical evidence or silently substitute paid downloads.

No production tag is issued: remaining C0–C9/T01–T30 requirements, full historical
source integration, other instruments, OOS/WFO, full autonomous research/dashboard,
security advisories and target-VPS gates are still listed in known-limitations.md.

## GitHub checks

The published application test and dashboard jobs passed. The original
GitHub dependency-review action failed because the private repository lacks the
required Advanced Security/dependency-graph feature. It is replaced with free
pip-audit and npm audit gates, preserving failure on detected vulnerabilities and
uploading the reports. No paid GitHub feature is enabled and no advisory is ignored.
The known fsspec/deepmerge findings still block production release.
