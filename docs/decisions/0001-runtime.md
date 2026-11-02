# ADR 0001 — development runtime and scope gate

Status: tested development selection; not a release approval.

The uploaded Factory.pdf is v2.0 (43 pages). Preserve original bytes. The named
Markdown original is absent, so BLUEPRINT.md is an explicit index, not a forged
copy. CODEX_BUILD_PROMPT.md is copied verbatim. User requests implementation,
which supersedes the earlier environment-only file-change restriction.

Use Python 3.12.14 and NautilusTrader 1.231.0, the compatible stable package
actually obtained from PyPI. Its installed .pyx documents a supported
get_orderbook_for_fill_simulation extension, used for deterministic adverse
liquidity prices. Matching, contingent brackets, accounts and fills remain in
Nautilus. No custom matching engine. Basic prob_slippage remains zero: it would
mean one tick, not two pips. Unit/integration fixtures verify actual engine fills.

The first Arrow 21 pin conflicted with Nautilus requiring >=25; the lock now
uses Arrow 25.0.0. uv.lock contains resolved artifact hashes. This is a development
selection, not a comparative engine-version benchmark on real Forex/Gold samples.
Nautilus requires Python >=3.12 here. Numba/VectorBT are not added before a measured
comparison. DuckDB is installed but analytical query integration is not complete.

Initial worker profile: one heavy child process; BLAS/Rayon threads set to one;
300-second timeout. Actual environment has cgroup 4 CPU quota and 32 GiB memory
limit, with ~60 GiB free workspace. It is Debian 13, not the user's Ubuntu Contabo.
An 8GB stress/soak and systemd resource enforcement remain required.

Synthetic profiles are named synthetic/v1, not asserted broker defaults. Money
conversion outside USD quote currency is currently explicitly unsupported.
Gold monetary/tick conventions are blocked on a verified instrument profile.

Local working branch: build/initial-factory. Git fetch works; GitHub metadata API
is denied. Existing AKYA77/hermes-factory is reused. Privacy, write access,
branch protection and PR creation remain unverified; no second repo is created.
