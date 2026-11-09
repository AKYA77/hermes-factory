# C0 branch rules — measured state and ready-to-apply configuration

C0's exit proof in `docs/implementation-plan.md` lists **branch rules** as a
remaining item, separate from the PUBLIC/private decision. This note records the
measured state and the exact configuration that would satisfy it, so the owner
can apply or decline it deliberately.

## Measured state

| Item | State | Evidence |
|---|---|---|
| Repository visibility | **PUBLIC** | `gh repo view AKYA77/hermes-factory` → `visibility=PUBLIC` |
| Branch protection, `main` | **none** | `GET /branches/main/protection` → 404 Branch not protected |
| Branch protection, `build/initial-factory` | **none** | `GET /branches/build%2Finitial-factory/protection` → 404 |
| Pinned Python packages | present | `uv.lock` (79 KB, committed) |
| Pinned JS packages | present | `apps/dashboard/package-lock.json` |
| CI job names | `audit`, `dashboard`, `python`, `verify` | `.github/workflows/*.yml` |
| `AGENTS.md` | committed | `59ac482` |

The repository is **public** while C0's criterion requires an *authorized private
repository*. Changing visibility is a repository setting the agent is explicitly
not authorized to change, so it is recorded here rather than performed.

## Why the rules were not applied by the agent

Branch protection changes repository governance state. The standing authorization
covers tested commits, pushes and exact-SHA PR/CI verification; it does not cover
repository settings. Applying it unasked would be a governance change of the same
class as the visibility change the agent is told not to make, so it is left to the
owner with the exact configuration below.

## Ready-to-apply configuration

Require the four current CI jobs to pass before a merge into `main`, disallow force
pushes and deletions. No review requirement and no push restrictions are
included, so the owner's own workflow is not blocked.

```sh
gh api -X PUT repos/AKYA77/hermes-factory/branches/main/protection \
  -F required_status_checks.strict=true \
  -F 'required_status_checks.contexts[]=audit' \
  -F 'required_status_checks.contexts[]=dashboard' \
  -F 'required_status_checks.contexts[]=python' \
  -F 'required_status_checks.contexts[]=verify' \
  -F enforce_admins=false \
  -F required_pull_request_reviews=null \
  -F restrictions=null \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```

Reversible with:

```sh
gh api -X DELETE repos/AKYA77/hermes-factory/branches/main/protection
```

## Effect on C0

Applying the configuration closes the **branch rules** item. C0 still cannot
reach its stated criterion while the repository is public and while the two
documented dependency advisories have no compatible fix; both are recorded in
`completion-ledger.json` under `C0`.
