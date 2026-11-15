# Real-source QA, process-death recovery and profile-aware search

Status: IMPLEMENTING_NOT_READY. SOFTWARE_VERIFIED, DATA_READY and OPERATION_READY
remain false. No release tag, production declaration or new publication.

Eight original HistData January 2025 partitions (21,345,746 quotes) passed the
complete bounded source-quality scan on clean commit df70a9e. Original source
and canonical bytes were rehashed, per-leaf stream digests/counts checked, and
all reported events retained. No canonical price, timestamp or order was changed.
All eight remain UNKNOWN_SPEC / UNKNOWN_CALENDAR and cannot authorize historical
strategy research. The 1,719 observed long interarrival gaps are not asserted to
be missing market ticks. Requested source periods were undeclared in this run.

Actual resource measurements: 171.809645s wall, 175.536930s process CPU,
184,852,480 bytes peak process RSS (176.289 MiB), 1,935,328 bytes generated QA
state, excluding original vault. Four CPU quota / 32 GiB cgroup; uncontrolled
page cache. This measures existing-source scanning, not download/import speed,
native strategy throughput, an 8 GiB limit or Contabo verification.

Actual authenticated loopback Chromium checks passed for eight real receipt
summaries, Gold counters, exact full-event download, desktop/mobile 390px layout
and no page errors. Browser screenshots and aggregate receipts are preserved in
reports/milestones/2026-11-04-source-quality/manifest.json. Raw provider quote
and event files stay local. The temporary loopback API has been stopped.

The following changes preserve existing architecture:

- Source QA now fsyncs attempt/input/code identity before stream reads. An actual
  SIGKILL child test proves no completed receipt is created and a fresh full
  retry preserves the orphan marker. Partial prefixes are never trusted as
  complete scans. Automated fenced QA/orphan inventory remains unfinished.
- search/v3 derives stop proposal units from declared pip/tick facts and the
  existing conservative feasibility geometry. Synthetic Gold with 0.001 tick
  and 0.1 pip samples 500..2300 ticks instead of a wholly infeasible 20..200.
  Native matching, risk, spread, slippage and exact intended 1:3 are unchanged.
- Legacy search/v1 and v2 distributions/hashes remain unchanged. Existing
  scientific-validation/v1/v2 explicitly keep v2 refits so their frozen identity
  cannot silently acquire different sampling. Scientific opt-in to the new
  search policy requires its own future protocol version.

Verification: bash scripts/verify.sh passed 302 tests, zero failures/skips,
348 retained third-party warnings, pytest time 82.08s. Ruff lint/format,
Svelte check and production static build passed. This includes actual native
Gold BUY/SELL fills at both search endpoints, exact 3R and modeled risk <=$2,
legacy identity/optimizer restart tests and the forced-kill recovery regression.
Focused search integration: 10 passed / 13.31s; focused unit/native monetary
suite: 57 passed / 1.75s. The first full invocation stopped at format checks;
three test files were formatted and the entire verification command rerun.
No checks were disabled. This verification excludes dependency audit commands;
the previously recorded Python and npm security failures remain unresolved.
Exact code/source identity and logs:
reports/milestones/2026-11-04-source-recovery-search/manifest.json.

Remaining work includes reviewed dated profile/calendar admission, corrections
and revisions, automated source workflows, genuine cost-aware screening, full
strategy-family/region generation and recursive diagnostics, full scientific
regime/global-inference/ranking gates, remaining dashboard and lifecycle/handoff
work, security fixes and actual target-host verification. The earlier 1,000-strategy
campaign remains separate synthetic evidence from its original pinned source;
it was not rerun or relabeled as historical evidence for this increment.

GitHub visibility was previously observed PUBLIC while private was requested.
Owner visibility decision remains pending; new commits remain local and pushes
are held. No visibility change or approval is inferred from elapsed time.
Next entry point: development-state.json, docs/completion-backlog.md and ADRs
0020/0021, followed by reviewed metadata/admission and source-version handling.
