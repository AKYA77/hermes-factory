# ADR 0002 — audited development dependency upgrades

Initial npm audit: 7 findings, including 2 high. Upgrade in one compatible set to
SvelteKit 3.1.1, Svelte 5.57.3, Vite 8.3.5, plugin 7.3.1, adapter 4.0.1, TypeScript
6.0.3 and svelte-check 4.7.8. SvelteKit 3 replaces svelte.config.js with Vite plugin
configuration and uses $app/tsconfig; those supported changes were applied.
No --force or legacy-peer-deps bypass was used. Fresh lock resolution preserved
registry artifact integrity. Current audit has 4 low dependency-chain findings
from the single deepmerge prototype-poisoning advisory GHSA-gcqx-w48m-w2h4;
no current patched upstream version is offered. Do not use an ancient suggested
major downgrade to silence the scanner. No untrusted Vite configuration is loaded.
This remains a release security issue, not a passed security gate.

Initial Python audit: 8 advisories in DuckDB, fsspec, pytest and Starlette.
Update DuckDB 1.4.2, FastAPI 0.162.0/Starlette 1.3.1 and pytest 9.2.0; lock and run
actual regression tests. The final scan still reports PYSEC-2026-4217 in fsspec
2026.2.0, which NautilusTrader 1.231.0 pins exactly. Fixed upstream fsspec is
2026.6.0. No dependency constraint was silently overridden. Current code does
not accept reference-filesystem JSON or invoke the vulnerable template path;
that restriction is not full release clearance. A maintained compatible engine
version or explicitly reviewed/tested dependency override is required before
production security acceptance. No production tag while this remains unresolved.

Raw scanner reports are ignored local evidence under reports/runtime. CI workflow
files exist but no remote scan or protected branch result is claimed.
