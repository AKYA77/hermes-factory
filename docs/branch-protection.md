# C0 branch rules — APPLIED 2026-11-10

C0's exit proof in `docs/implementation-plan.md` lists **branch rules** as a
remaining item, separate from the PUBLIC/private decision. Both are now closed:
the owner ruled the repository stays public (ADR 0070), and `main` is protected
as recorded below.

## Applied state

| Item | State | Evidence |
|---|---|---|
| Repository visibility | **PUBLIC** (owner-directed) | ADR 0070; `gh repo view AKYA77/hermes-factory` |
| Branch protection, `main` | **applied** | `GET /branches/main/protection` |
| `required_status_checks.strict` | `true` | measured |
| `required_status_checks.contexts` | `audit`, `dashboard`, `python`, `verify` | measured from `.github/workflows/*.yml` |
| `allow_force_pushes` | `false` | measured |
| `allow_deletions` | `false` | measured |
| `enforce_admins` | `false` | measured |
| `required_pull_request_reviews` | none | measured |
| `restrictions` | none | measured |
| Branch protection, `build/initial-factory` | none | not required; the PR targets `main` |
| Pinned Python packages | present | `uv.lock` |
| Pinned JS packages | present | `apps/dashboard/package-lock.json` |

`enforce_admins` is deliberately `false` and no review or push restrictions are
set, so the owner's own workflow is not blocked. Force-pushes and deletions are
disabled, so reviewed history cannot be rewritten.

## Superseded reading

An earlier version of this note recorded the repository as public while C0
required an authorized private repository, and left the rules unapplied because
repository governance was outside the standing authorization. The owner's
2026-11-10 instruction supersedes that: the repository remains public
(`docs/decisions/0070-public-repository-owner-amendment.md`) and the rules were
applied. The original blueprint text is preserved unchanged.

## Reversibility

```sh
gh api -X DELETE repos/AKYA77/hermes-factory/branches/main/protection
```
