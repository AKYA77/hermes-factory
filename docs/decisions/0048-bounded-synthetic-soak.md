# ADR0048 — Bounded synthetic soak run

Status: implemented software scope; T24 full acceptance open.

## Problem

T24 requires a representative soak test below set limits, with no OOM, no
uncontrolled swap and archived metrics. The existing benchmark was explicitly
scoped `NOT SOAK`, so no soak evidence existed.

## Decision

`factory/operations/soak.py` repeats a bounded synthetic work cycle — synthetic
generation followed by a fresh worker replay — and samples resident memory and
swap usage throughout.

- `iterations` bounds the run; `max_rss_bytes` (default 8 GiB) and
  `max_wall_seconds` (default 3600) bound resources.
- A cycle that exceeds the RSS limit is killed and recorded as
  `STOPPED_RSS_LIMIT`; a run that exceeds the wall limit stops and records
  `STOPPED_WALL_LIMIT`.
- The report is archived to the requested output path with peak RSS, peak swap,
  wall time, limits, `within_limits`, `oom_detected` and `uncontrolled_swap`.
- CLI `soak` with `--iterations`.

## Safeguards

- Scope is `NOT VPS / NOT HISTORICAL / NOT MARKET VALIDATION`.
- Synthetic fixture only; no Forex/Gold corpus.
- Sampled RSS at 20 ms may miss shorter peaks.
- Swap presence is reported, not treated as failure.
- No 8 GB stress claim beyond the configured limit.

Evidence: docs/milestone-historical-screen-cohorts.md.
