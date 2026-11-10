# ADR 0070 — Repository remains PUBLIC; branch protection applied

- Status: accepted
- Date: 2026-11-10
- Supersedes: the private-repository expectation in C0
- Owner authority: explicit owner instruction, 2026-11-10

## Context

C0's original exit proof required an **authorized private repository** plus
branch rules. At the time this repository was created it was public, so C0 was
recorded as `FAIL` with two parts: the visibility mismatch and the absence of
branch protection.

The owner has now issued an explicit, final instruction: **the repository must
remain public**. The private-repository expectation is superseded. This ADR
records that decision so the historical blueprint is not falsified or deleted,
and so C0 can be assessed against the corrected criterion.

## Decision

1. `AKYA77/hermes-factory` remains a **public** repository. Visibility is not to
   be changed.
2. C0 is reassessed as: *is the repository securely governed as an authorized
   public repository?*
3. Branch protection is applied to `main` using the verified CI context names,
   without locking out legitimate owner maintenance.

## Applied configuration

Measured after application via `GET /branches/main/protection`:

| Setting | Value |
|---|---|
| `required_status_checks.strict` | `true` |
| `required_status_checks.contexts` | `audit`, `dashboard`, `python`, `verify` |
| `allow_force_pushes` | `false` |
| `allow_deletions` | `false` |
| `enforce_admins` | `false` |
| `required_pull_request_reviews` | none |
| `restrictions` | none |

`enforce_admins` is deliberately `false` and no review or push restrictions are
set, so the owner's own workflow is not blocked. Force-pushes and deletions are
disabled, so the reviewed history cannot be rewritten.

The four required contexts are the workflow job names measured from
`.github/workflows/*.yml`, not assumed.

## Consequences

- C0's visibility component is **closed** by owner decision, not by changing the
  repository.
- C0's branch-rules component is **closed** by the applied protection.
- The two documented dependency advisories (fsspec, deepmerge) remain with their
  own measured dispositions and are unrelated to C0's governance criterion.
- The original blueprint text is preserved unchanged; this ADR is appended as the
  authoritative current reading.

## Reversibility

The protection can be removed by the owner with:

```sh
gh api -X DELETE repos/AKYA77/hermes-factory/branches/main/protection
```
