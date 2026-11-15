# ADR0026 — Admission-bound historical research protocols

Status: implemented for development verification; no release readiness claim.
Authority: original v2.0 blueprint, reviewed-input ADR0022, and the owner’s final
software/handoff directive, archived 4 November 2026. The owner authorizes the
builder to verify primary facts and explicitly declare generic research models;
this does not authorize invented historical broker specifications.

The worker already accepts reviewed non-synthetic inputs, but search, protected
confirmation and scientific refits previously stopped at synthetic-only schema
guards. Extend those interfaces without reinterpreting stored legacy identities:
search/v4 requires a non-synthetic profile and admission; protected-holdout/v2
carries an admission; scientific-validation/v3 propagates that admission through
refits, stage evaluation and one-time confirmation. Earlier search/holdout JSON
omits the new optional field. Older scientific protocols keep their original
search/v2 distribution; v3 uses pip-aware search/v3 for synthetic inputs and v4
for historical inputs.

Historical-approved/v2:<admission SHA>:<scope SHA> binds immutable reviewed
references to a particular optimizer, evaluation stage or protected holdout.
The v1 policy remains strictly one SHA. Registration, generation, worker start,
worker completion, holdout freeze/authorization and evaluation recheck references,
source integrity and revocations. Historical screening is disabled until a
separately verified historical screening policy exists; the synthetic cost-shadow
policy does not silently migrate to real data.

A completed historical protocol is not automatically a scientifically validated
strategy. Global selection and regime robustness remain release requirements;
reports expose promotion blockers and cannot enter the historical validated
board. Synthetic protocol success remains software-reference evidence only.
Generated non-synthetic-flag fixtures are conspicuously TEST_ONLY; they test trust
boundaries, not market performance. Genuine provider rehearsal is recorded
separately with its actual references, assumptions, prior use and measurements.

Nanosecond windows now use the same exact integer boundary type as calendars:
integers and decimal integer strings retain every digit; floats, booleans,
scientific notation strings and values outside signed-int64 range are rejected.
Valid stored integer contracts retain their identities. This is strict input
validation, not a change to split dates, costs, risk, formulas or execution v4.

The optional generic FX profile declares base-unit quantity, a one-unit cap,
unlevered margin and empirical research grid as model assumptions. Published
currency/pip conventions are cited separately. It is not an account profile;
actual risk may be below the unchanged requested 10% budget. Gold is excluded
pending an independent units/cost-equivalent definition. A generic weekly session
envelope cannot certify provider holidays or daily maintenance.
