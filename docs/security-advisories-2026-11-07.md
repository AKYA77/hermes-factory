# Dependency security disposition — 2026-11-07

Verified against the actual committed lockfiles, the installed environment and a
runtime module check on this host. This supersedes the older
`UNRESOLVED_BLOCKING` note in `development-state.json` with a measured
disposition. No advisory is suppressed and no incompatible pin is overridden.

## 1. fsspec 2026.2.0 — GHSA-27vj-qcqg-25rc

**Advisory.** Server-Side Template Injection in
`fsspec.implementations.reference.ReferenceFileSystem` leads to remote code
execution. Externally supplied Kerchunk/reference JSON is rendered through
unsandboxed `jinja2.Template(...).render(...)`. Affected from `0.9.0` onward.

**Constraint.** `nautilus_trader==1.231.0` declares an exact pin
`fsspec==2026.2.0`. The project's own `pyproject.toml` does not add fsspec.

**Compatible fix.** None without overriding an upstream pin. A newer fsspec
would violate `==2026.2.0`, so it cannot be selected without either a Nautilus
release that relaxes the pin or an explicit owner decision to accept a
constraint override. Neither is done here.

**Reachability — measured.**

- `grep` over the installed `nautilus_trader` package finds no import of
  `fsspec.implementations.reference` or `ReferenceFileSystem`.
- Nautilus uses `fsspec.filesystem("file")`, `fsspec.filesystem("github", ...)`,
  `LocalFileSystem` and `MemoryFileSystem` only.
- Loading `nautilus_trader` and the project's simulation runner loads
  `fsspec.implementations.local` and `fsspec.implementations.memory`;
  `fsspec.implementations.reference` is **not** imported.
- The project's own code never references fsspec outside a report string.

**Impact.** The vulnerable sink is unreachable in this system. There is no path
from the historical/paper research workflow to `ReferenceFileSystem`.

**Residual risk and required review.** Low. Residual risk is a future Nautilus
release routing data loading through the reference filesystem. Required review:
re-run this reachability check on every Nautilus upgrade, and re-assess if the
project ever ingests externally hosted Kerchunk/reference catalogs. Owner
decision required before any pin override.

## 2. deepmerge (npm) — GHSA-gcqx-w48m-w2h4

**Advisory.** `deepmerge` `mergeObject()` allows prototype poisoning of
returned objects. Affects `>=4.2.0`.

**Constraint.** `deepmerge` is not a direct dependency. It enters through
`@sveltejs/vite-plugin-svelte` → `@sveltejs/kit` → `@sveltejs/adapter-static`,
all **build-time dev dependencies** of the dashboard.

**Compatible fix.** None. `4.3.1` is the latest published version and is inside
the affected range. `npm audit fix --force` proposes `@sveltejs/kit@0.0.30`, a
breaking downgrade; not applied.

**Reachability — measured.** `npm audit` reports 4 low-severity findings, all
through that build chain. `deepmerge` is not present in the built dashboard
bundle: it is a Vite/Svelte plugin dependency executed at build time on trusted
local source, and it is not shipped to or executed by dashboard clients.

**Impact.** No runtime exposure. The prototype-poisoning sink cannot be reached
by dashboard users or by the API.

**Residual risk and required review.** Low. Required review: re-run
`npm audit` on every dashboard dependency update, and re-assess if a fixed
deepmerge is published or if build tooling begins merging untrusted input.

## Disposition summary

| Advisory | Package | Fixed version | Reachable | Disposition |
|---|---|---|---|---|
| GHSA-27vj-qcqg-25rc | fsspec 2026.2.0 | none compatible with the exact Nautilus pin | No — sink never imported | Documented residual risk; re-check on Nautilus upgrade |
| GHSA-gcqx-w48m-w2h4 | deepmerge (npm) | none published | No — build-time only | Documented residual risk; re-check on dependency update |

No security auditing is disabled. CI continues to run dependency checks.
`SOFTWARE_VERIFIED`, `DATA_READY` and `OPERATION_READY` remain false.
