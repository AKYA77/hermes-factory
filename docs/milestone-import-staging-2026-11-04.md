# Import staging lifecycle — NOT_READY

Baseline published commit:66fa06c18984dc7b77825b7f3528fa3ac66fbb4d.
ADR0028 adds bounded payload admission and safe duplicate-staging reclamation.
Tested scientific source SHA256:
`aa1f3edafea885b7c88bcc310ad9d870a342dd50766ed13d5b2cd1c6b7117aa3`.
No financial execution, source quote, risk, ranking or validation formula changed.

## Actual software and proof

Import payload writes now share a catalog-wide nonblocking lock and a default
2GiB budget; `--staging-budget-bytes` is an operational override. Each bounded
compressed chunk is checked before writing. Failed/orphan payloads and other
import intents count; sources/results are never evicted. JSON audit/checkpoint
metadata is excluded and remains separately bounded at the individual checkpoint
level. This is not an OS filesystem hard quota or total canonical-archive quota.

Successful publication records the exact canonical manifest hash. An explicit
trusted-local command deeply verifies source, provenance and canonical identity,
then removes only checksum-matching duplicate chunks listed in that checkpoint.
An immutable request and durable reclamation marker precede unlink; completion
gets a separate immutable result. An interrupted operation can resume without
recreating chunks or modifying a canonical file. Failures and uncheckpointed
orphans remain. Corrupt source/staging and symlinked paths fail closed. Final
source verification is required again before reusing a reclaimed import.

Generated tests cover payload rejection with no data write, changed-budget
resume, other-intent/orphan accounting, the shared admission lock, explicit CLI,
repeated reclamation, interruption after one unlink, request without success
receipt, source/chunk corruption and path containment. Existing SIGKILL import
and parser precision regressions still pass. Full verification:

- `bash scripts/verify.sh`: exit0,384passed,0failed/0skipped,362warnings,
  pytest161.097s; Ruff lint/format, Svelte diagnostics and dashboard build pass.
- Focused affected suite:60passed/2warnings,2.99s.
- Wrapper:165.362769s wall,167.132045s child CPU,
  maximum child process RSS962,965,504B (not aggregate tree memory).
- Generated50,000-row import measurement: uninterrupted0.800356s;
  checkpointed first1.001679s; full-prefix reuse0.763931s. All dataset IDs match.
  Maximum process high-water RSS216,625,152B; disk1,435,051B before reclamation.
- Actual reclamation CLI removed7chunks/359,384B in0.374190s wall,
  0.677053s child CPU,138,137,600B peak child RSS. Every canonical file hash
  remained identical and a fresh deep catalog check verified50,000rows.

Measurements use generated fixtures and uncontrolled OS page cache. Concurrent
full-suite work was present; these are not target-host, cold-cache, market-data
or native tick-replay throughput measurements. No universal speedup is claimed.

[Hashed evidence](../reports/milestones/2026-11-04-import-staging/manifest.json)
retains full/focused logs, current XML, measured import/reclamation resources and
prior exact-commit CI observations. The reproducible commands are in
[the backfill runbook](runbooks/historical-backfill.md). No bulk acquisition ran.

## Publication, security and remaining work

The baseline66fa06c was pushed and PR#1 head independently matched via the public
GitHub page. Exact-commit push workflow runs41928921357(Python) and41928921338
(dashboard) passed. PR dependency review41928927229 failed on the known
fsspec/deepmerge advisories; its page identifies66fa06c. New source CI is checked
after publication of this increment; prior CI must not be substituted for it.

Actual proxy checks denied HistData, OANDA and SIX HTTPS access with CONNECT403.
GitHub API access also returned Forbidden; public PR/actions pages and Git work.
The existing environment draft now additively includes histdata.com,
www.histdata.com,www.oanda.com,www.six-group.com,api.github.com; package presets
and other settings were preserved. Draft persistence is confirmed, but the
network changes are not applied or published. Review/save/publish in environment
settings is needed before retrying primary-source/genuine-profile access. No
secret is requested or assumed missing.

SOFTWARE_VERIFIED,DATA_READY,OPERATION_READY remain false. Mandatory remaining
implementation includes scheduled acquisition/source refresh, canonical storage
retention/compaction and full source APIs/UI; Gold/all-instrument references and
provider fidelity; global/regime/comparable scientific qualification; all-family
autonomous discovery and safe calibrated screening; complete diagnosis and
responsive graphical workflows; installed lifecycle/off-host recovery/security,
reproducible release and Hermes handoff. Actual Contabo/8GB/reboot/soak is unrun.
This is a pushed development checkpoint, not final completion of the mandate.
