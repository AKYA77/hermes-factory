## Unreleased

### Changed

- Case generation, normalization and comparison for the Rust engine parity
  tooling moved to a Nautilus-free module (`scripts/raptor_cases.py`), so
  `scripts/verify_raptor_goldens.py` no longer imports NautilusTrader. The frozen
  goldens remain verifiable after removal: running the verifier with any
  `nautilus_trader` import blocked still reports 240/240.

### Added

- The Rust execution engine is now resumable: its replay state serializes to
  JSON and restores exactly, and the CLI gained `--batch-size`, `--dump-state`
  and `--resume-from`. `scripts/parity_raptor_restart.py` proves batch sizes
  1/2/3/7/64 and a cross-process restart at a quote boundary all reproduce the
  single-pass result exactly (240/240), and that result still matches the Python
  reference.

### Fixed

- The Rust execution engine now reproduces partial fills against a finite eligible
  book, including the reference's partial-entry bracket cancellation and safety
  close, repeated timeout re-submission, size-increment rounding before and after
  the book cap, and quantity-weighted multi-fill exit prices. Order states and
  exit reasons are emitted. Verified exact on 240/240 finite-book fixtures,
  800/800 unbounded fixtures and 30/30 genuine acquired partitions.

# Development log

## 0.1.0.dev0 — unreleased

Initial partial implementation: preserved v2.0 PDF/build directive; typed
contracts; exact fingerprints; quote catalog/quarantine; durable leased queue;
Nautilus adverse-fill adapter/brackets; shared closed-bar operators; bounded
proposals/children; excursion diagnostics; frozen-window replay helper; basic
metrics/boards; authenticated API and connected SvelteKit state inspector;
consistent SQLite backup rehearsal and atomic release-pointer test harness.

No release, no historical-data results and no claim of C0–C9 completion.

### 2026-11-12 — owner Lean RaptorBT directive (ADR 0071)

Recorded the owner's latest design directive and completed Phase 0: versioned
amendment `docs/source/Owner_Lean_RaptorBT_Final_Directive_2026-11-12.md`, ADR
0071, measured inventory `docs/inventory-2026-11-12.md`, twelve new acceptance
gates R01–R12 (79 total), and queue task `raptorbt_execution`. NautilusTrader
becomes a migration target rather than the permanent matching engine; dynamic
M1–D1 selection, one accurate pipeline, a strict 50% gate and a native Rust
generator are now mandated. No gate is claimed passed and no readiness state
changes.

### 2026-11-12 — Phase 1 Rust execution engine, exact parity

Added `rust/raptor-engine/`: a from-scratch Rust execution engine with
arbitrary-precision rational arithmetic, exact bid/ask pricing, the 2-pip
spread floor plus separate 2-pip adverse slippage, risk-based sizing and
sequential bracket replay. `scripts/parity_raptor_engine.py` proves it
reproduces the Python reference exactly — 100/100 EURUSD, 240/240 and 800/800
all-instrument generated fixtures, comparing prices, quote indices, roles,
flags, exit reasons, sizes and P&L as exact rationals. Six real defects were
found and fixed, including a silently wrapping `i128` rational comparison and an
off-by-one in 28-significant-digit rounding. R01–R03 gain scoped evidence and
remain `NOT_TESTED`; NautilusTrader is not removed. See
`docs/milestone-raptor-engine-parity-2026-11-12.md`.
