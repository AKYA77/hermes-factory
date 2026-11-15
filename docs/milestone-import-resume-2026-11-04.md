# Retained-archive recovery and exact source decoding — NOT_READY

Baseline remote: e9c30e49027d26ffc609240976dc5b2c9e9fccd3. ADR0027 implements
checkpointed intra-partition decoding, not HTTP Range resume or full C2 acceptance.
The exact tested scientific source hash is
`a7021654549e9d11a40c5279ff96b0a118de6dfffca4b7ccb4cc989c3e123f0b`.
All previous source/experiment records, execution v4, costs and scientific gates
are retained. No risk, ranking, holdout or monetary assumption was changed.

The import CLI now retains fsynced, checksummed Parquet chunks and raw-prefix
cursors under the catalog's `.imports/` area. A retry verifies every prefix and
chunk before parsing only the remainder, then uses the existing full streaming
verifier for publication. Invalid sources and incomplete chunks cannot become
catalog datasets. Original data/v2 manifest/quote/Parquet identities agree with
uninterrupted imports in generated EURUSD/JPY/Gold-shaped fixtures. A real child
is SIGKILLed after a durable chunk; restart parses only remaining rows and
preserves duplicate/tied source records. Source/chunk/checkpoint corruption,
forged cursors, concurrent admission, disk reserve and publication failure are
covered. Staging consumes additional retained disk; safe cleanup remains open.

A reproduced parser/v1 defect accepted a source price with fractional digits
beyond the integer grid after Decimal context rounded them away. Parser/v2 uses
bounded exact integer-ratio conversion. Precision2/6/28/60 and extreme-exponent
regressions pass. Existing valid quote values and old partitions are unchanged;
new parser provenance receives a new dataset identity. Previously discarded
precision cannot be reconstructed from canonical values alone. A separate final
publication guard rejects a raw-source swap between prefix verification and
catalog intake.

Verification: `bash scripts/verify.sh`, exit0, **376passed, zero failures/skips**,
362 retained third-party warnings, pytest165.689s; lint/format and dashboard
check/build pass. Total wrapper wall170.314832s, child CPU170.665130s, maximum
child process RSS949,399,552B. This is not aggregate worker RSS or target-host
acceptance. The earlier pre-parser full run365passed is retained separately;
final verification was rerun because the parser and publication guard changed.
Focused affected suite52passed/2warnings. Exact receipts and hashes are in
[the manifest](../reports/milestones/2026-11-04-import-resume/manifest.json).

Reproduce the generated import measurement with:

```bash
.venv/bin/python scripts/benchmark-import-resume.py \
  --output reports/runtime/import-resume-benchmark.json
```

50,000generated millisecond rows: uninterrupted0.792690s wall/0.795827CPU;
checkpointed first0.973527s/0.972679CPU; verified-prefix reuse0.758404s/0.772184CPU.
All produce the same dataset identity. Prefix reuse decodes0additional rows,
rechecks50,000raw-prefix rows and performs final canonical verification. Total
benchmark disk1,434,870B; process high-water RSS215,900,160B. OS page cache is
uncontrolled; this is not a cold/warm statistical comparison, native replay
throughput, historical data or a universal speedup. First-pass checkpointing adds
work in exchange for durable recovery. No expensive research campaign was rerun.

Security rechecked: pip-audit exit1 for fsspec2026.2.0/PYSEC-2026-4217; npm audit
exit1 for deepmerge4.3.1/GHSA-gcqx-w48m-w2h4 and its dependency chain. Current
PyPI Nautilus remains1.231.0 with the exact vulnerable fsspec pin. No unsupported
override, ancient dashboard downgrade or disabled audit was applied. Both gates
remain release-blocking. `gh api` returned Forbidden; public GitHub PR/actions
pages returned HTTP200 and confirmed baseline PR head. Publication/current-head
CI must be verified separately after pushing this increment.

All readiness states remain false. Full source calendars/Gold references,
scheduled refresh and storage operations, global/regime validation, full strategy
families/autonomous discovery/calibrated funnel, full graphical diagnostic UI,
installed lifecycle/security/reproducible release and target-host gates remain.
The new uploaded owner request is archived in source/Final_Completion_Task_2026-11-04.md.
