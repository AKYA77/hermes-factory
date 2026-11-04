# Reviewed historical research inputs and revocation

Status: scoped implementation; not full C2/C3/C6 or a historical-validation claim.
Authority: blueprint §§6.3/6.5 and owner Persistent Software Completion Goal §§1–2.

Migration008 adds immutable reference/admission records and permanent revocations.
Captured documents are content-addressed, limited to 16 documents of 4 MiB each.
A profile review requires explicit citations for every monetary/unit/volume/margin
field, effective UTC scope, reviewer and attestation. A citation distinguishes a
published fact from an explicit hypothetical research assumption. Those are never
interchangeable. Calendar review captures the original TZif bytes and source
reference. Software verifies hashes/bindings; an accountable human operator must
review document meaning, dated applicability and the legitimacy of assumptions.
No LLM proposal or source decimal precision constitutes reference approval.

A source admission binds exact profile/calendar review IDs, source-QA receipt,
full QA event hash, declared period and substantive acceptance notes. Structural
issues, off-grid observations, unknown/closed calendar rows, undeclared expected
periods, wrong units/instruments or out-of-scope references block admission.
The reviewer accepts all observed QA events, including boundary/unquoted interval
warnings; this is not proof of complete tick coverage or broker executability.
The original QA receipt remains declaration-level and immutable; reviewed
acceptance is a separate record, not an overwritten historical_admission flag.

New contracts opt in with evaluation_policy = historical-approved/v1:<admission_id>.
The admission is therefore part of experiment identity, never an untracked payload
flag. The training worker and fixed-window evaluator check source kind, hashes,
references, time scope and revocations before/after actual Nautilus replay.
Evaluation includes its full prior-only warm-up in admission scope. Official
finalization checks admission dependencies again under the same SQLite writer
lock as completion, preventing a revocation/finalization race. Old completed
results remain preserved after revocation; current use is blocked. There is no
automatic independently-validated promotion.

This changes eligibility software, not prices, native fills, costs, risk, intended
1:3 distances, statistical thresholds or existing synthetic experiment semantics.
Existing synthetic training and validation paths remain unchanged. Search/TPE,
scientific-validation protocols and protected confirmation still need versioned
propagation of historical admission; the existing exact-zero screen explicitly
refuses historical input until its separate historical policy is implemented.
Do not describe these remaining paths as integrated historical autonomous research.

Trusted local operator commands:

1. reference-register REVIEW.json DOCUMENT... [--tzif CAPTURE.tzif]
2. source-quality DATASET POLICY.json --profile PROFILE.json
   --calendar-spec CALENDAR.json --tzif CAPTURE.tzif
3. source-admit ADMISSION.json [--catalog VAULT]
4. input-reviews [--limit 50 --offset 0]
5. input-revoke REVIEW_ID --actor OPERATOR --reason REASON

Prefix all with `.venv/bin/python -m factory.cli --state STATE`. Review/admission
JSON schemas are ReferenceReview and AdmissionSpec in factory/data/admission.py;
source_quality policy declares the exact period. Preserve the source vault and
artifacts/references in backups. No remote write endpoint accepts approvals or
measured metrics. Authenticated GET /api/v1/input-reviews and /{id} expose bounded
summaries and byte-verified exact exports. The connected Market data view shows
declared assumptions, effective scope, revoked dependencies and empty states.

Tests use conspicuously generated TEST_ONLY documents, profiles and paths, with
non-synthetic flags specifically to exercise the authorization boundary. They
prove actual native worker eligibility and failure checks, NOT genuine historical
market validation, legitimate broker references or owner approval of a venue.
The existing real January data remains unapproved pending actual reviewed facts.

Full verification: scripts/verify.sh exit0, 310 passed, zero failures/skips,
354 retained third-party warnings, pytest85.15s; Ruff lint/format, Svelte check
and static build pass. Evidence/source hashes are preserved in
reports/milestones/2026-11-04-reviewed-inputs/manifest.json. Browser proof follows
on the clean committed source. Security audits are separate unresolved gates.
