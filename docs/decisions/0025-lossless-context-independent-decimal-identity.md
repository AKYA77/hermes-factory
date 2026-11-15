# Exact Decimal fingerprint encoding

Status: correctness fix; canonical Decimal expansion is bounded; no risk/cost/fill,
ranking, validation threshold or existing stored result is changed.
Authority: blueprint canonical identity/reproducibility/immutable-evidence gates.

The former Decimal.normalize() call rounded according to the active Decimal
arithmetic context. At28digits,1.0000000000000000000000000001 and
1.0000000000000000000000000002 received the same serialized value and fingerprint.
A1.23456789 input also received different fingerprints under precision6 vs28.
This was input-encoding loss, not a cryptographic SHA256 collision.

Encoding now uses exact fixed-point text formatting and strips only trailing
fractional zeros/the trailing decimal point. It performs no numeric rounding.
Equivalent padded representations still match. Existing signed-zero spelling is
retained for compatibility. Nonfinite inputs still reject. Coefficient digits
plus absolute exponent may not exceed16,384; over-budget values reject before
formatting, preventing a tiny exponent string from allocating gigabytes. This
fails visibly and never truncates a scientific value. Source quote storage stays
exact integers and is unaffected.

Correctly representable old encodings remain identical; stored IDs/JSON/history
are not rewritten. Ambiguous historical pre-normalization inputs, if any existed,
cannot be recovered after old software discarded their precision. Do not invent
those original values or certify them retrospectively. Old artifacts remain as
recorded and the old code remains in Git. New distinct exact inputs now have
distinct canonical representations.

Read-only compatibility inventory:42local SQLite states;16,177strategy specs,
16,247experiment contracts and26instrument profiles (32,450typed records).
No encoding differences or parse errors among these retained typed values. This
is not proof of unretained pre-normalization inputs, all Git history, or that
16,247contracts represent executed backtests. No database was rewritten.
Reproduce with scripts/verify-decimal-identity.py. Tests explicitly cover context
precision2/6/28/60, high-precision differences, equivalent padding, old goldens,
signed zero and billion-exponent resource rejection.

Cost-label score presentation also uses explicit Decimal28/HALF_EVEN context;
its underlying sums/variance are rational. Full suite after these changes:
337passed,zero failures/skips,362warnings,89.94s,lint/format/frontend pass.
All readiness and release gates remain unchanged/false until the full application
and remaining required verifications are complete.
