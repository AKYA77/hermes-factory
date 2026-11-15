# Source quality receipts and captured calendar rules

Status: scoped software tests pass; real-source resource run/browser proof follow
this code commit. Full C2, metadata approval and SOFTWARE_VERIFIED remain open.
Authority: blueprint source fidelity/calendar/immutable evidence requirements and
owner completion mandate sections 4–5. Canonical source bytes, prices, timestamps
and event ordering remain unchanged. No backtesting engine is added.

SessionCalendar uses captured TZif bytes bound by SHA256, dated effective periods,
explicit weekly sessions/closures and an explicit ambiguous-boundary policy.
Missing/nonexistent/unsupported rules remain unknown. Nanoseconds are exact ints
or exact decimal strings; floating/bool timestamp inputs reject. Rules use integer
UTC arithmetic. A prepared interval union/prefix representation bounds memory
and avoids timezone conversion per quote. DST goldens cover 47/49-hour weekends,
one-nanosecond boundaries, closures and ambiguous/nonexistent local times.
Declared rules are not automatically verified broker facts.

SourceQuality performs one bounded 8,192-row pass over canonical quotes. It
verifies per-leaf semantic stream hashes/counts, rehashes original source and
Parquet bytes, checks precision/order/units and retains duplicate observations.
Every internal gap, requested boundary interval, issue and declared-session run
is retained in a hashed JSONL artifact. Display examples are bounded; complete
artifacts are not silently truncated. Unchanged observations are warnings, not
proof of staleness. Long interarrival/boundary intervals are not proof that a
market tick is missing. Optional expected periods distinguish undeclared scope
from actual observations outside the requested period.

Captured calendar JSON, original TZif bytes and declared profile JSON accompany
the receipt and are checked on reuse. Migration 007 preserves immutable input,
report/event hashes, attempts/failures and measured resources. Source artifact
files and directory are fsynced before receipt publication. Interrupted/budget-
limited scans retain partial events and an explicit incomplete failure. Cached
receipts are byte-checked against immutable database hashes, not trusted by mtime.
Corruption returns an error rather than silently replacing old evidence.

Historical admission is always false for this declaration-level receipt version.
Unknown metadata remains UNKNOWN_SPEC/UNKNOWN_CALENDAR; declarations remain
DECLARED_* and are not promoted into verified broker profiles. Reviewed source
metadata/registry admission, revisions, native session integration and full source
completeness remain separate mandatory work. Keep the preserved canonical vault
when backing up an isolated QA state; receipt artifacts do not replace source data.

Producer: `hermes-factory --state STATE source-quality DATASET POLICY.json`
with optional `--catalog VAULT`, `--profile PROFILE.json`, and paired
`--calendar-spec CALENDAR.json --tzif CAPTURE.tzif`. See the explicit policy example
in config/source-quality-policy.example.json. Zero exit means complete technical
scan without structural/declared-unit/calendar/period mismatches, not historical
approval. Incomplete scans and those mismatches exit nonzero; unknown absent
metadata is disclosed in the result and cannot approve research.

Authenticated read interfaces: GET /api/v1/data/quality (paginated structured
counts), /data/quality/{id} (verified receipt), /data/quality/{id}/events (exact
streamed JSONL), /data/quality-attempts (paginated failures/resources). Corruption
returns 409; there is no metric-write endpoint. The connected Market data panel
shows actual scope/counters/unknown states, failures and exact artifact downloads.
Large source computation currently runs through the supported local CLI; fenced
scheduled data admission and metadata-review controls remain unfinished.

Verification: bash scripts/verify.sh — 287 passed, zero failures/skips, 340
recorded third-party warnings, 79.66 seconds; Ruff/frontend checks/build passed.
Includes all-gap retention beyond examples, tied/view source references, cache
restart, corruption rejection, incomplete budget retention, source-sequence
faults, declared off-grid values without rounding, captured-input tampering,
actual CLI exit/status behavior and authenticated exact API export. Existing
migration assertions now include additive schema 7; no test or security gate
was disabled. The original data.quality helper remains intact; the new module
is data.source_quality to avoid shadowing that existing API.

Clean-source df70a9e measurement: the eight actual January imports (21,345,746
quotes) completed structural stream QA in 171.809645 wall seconds and 175.536930
process CPU seconds, at 184,852,480 bytes peak process RSS. Generated QA state
was 1,935,328 bytes, excluding the original source vault. This environment has
four CPU quota and 32 GiB memory; page cache was uncontrolled. This measures
source scanning, not acquisition, native backtesting or target-host throughput.
All profiles/calendars remained UNKNOWN and historical admission remained false.
Actual authenticated Chromium desktop/mobile checks passed for all eight receipt
summaries, Gold counters, exact event export and no overflow/page errors. Evidence:
reports/milestones/2026-11-04-source-quality/manifest.json. Raw provider quotes
and event artifacts remain local; only aggregate evidence is committed.

Abrupt process-death correction: every new scan now fsyncs attempt.json, its
input/code/policy identity and its parent directory before opening the source
stream. A SIGKILL test kills the actual child after its first source row, proves
there is no completed receipt, and verifies a fresh full 32-row retry leaves
the original marker unchanged. Partial files are never treated as a resumable
semantic prefix. An orphan has no database failure row because SIGKILL cannot
run cleanup; attempt.json remains identifiable, not proof that a process is dead.
Automatic fenced QA scheduling/orphan inventory remains unfinished. Recovery:
retain .pending-* artifacts, inspect their attempt.json, and retry the original
source-quality CLI; a complete receipt requires rechecking the full source.
