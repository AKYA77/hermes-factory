# ADR0040 — Market volatility regime cohorts

Status: implemented software scope; full scientific acceptance open.

## Problem

The blueprint requires volatility and regime cohorts. ADR0037 added equity
regimes derived from the trade sequence, but no market-data volatility
classification existed, so performance could not be read against prevailing
market volatility.

## Decision

`factory/diagnostics/market_regimes.py` builds a descriptive volatility regime
classifier from canonical M1 midpoints:

- `load_m1_midpoints` reads the retained canonical Parquet and takes the last
  midpoint of each whole UTC minute inside the reviewed training window;
- `realized_volatility` computes the trailing standard deviation of log returns
  over a 60-minute window;
- `regime_classifier` maps each minute to `LOW` / `NORMAL` / `HIGH` using the
  window's own 33rd and 67th percentiles;
- `regime_of` resolves a trade entry timestamp to its prevailing regime,
  tolerating the warm-up minutes where no trailing window exists.

`DiagnosticCohorts.report` now builds this classifier from the experiment's own
admitted dataset and window, and the aggregate reports a `volatility_regimes`
cohort alongside the existing sessions, sides, equity regimes, stop classes,
failure patterns, excursions, hold durations and drawdown/recovery statistics.
The thresholds and window are reported with the result.

## Safeguards

- Regimes are **relative to the reviewed training window**, not absolute or
  broker-calendar classifications.
- Only the experiment's own admitted canonical dataset and training window are
  read; no protected evaluation or holdout window is touched.
- A missing or unreadable dataset yields `volatility_regimes: null` rather than
  an invented classification.
- `descriptive_only` remains true. Volatility regimes never qualify, rank or
  promote a strategy.

Evidence: docs/milestone-historical-screen-cohorts.md.
