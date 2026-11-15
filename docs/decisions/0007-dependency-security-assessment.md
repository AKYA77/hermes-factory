# Dependency-security assessment — gates remain failing

No scan is disabled, ignored, downgraded in severity, or converted to a passing
release gate. Fresh pip-audit/npm audit observations remain:

| Finding | Installed path | Assessment and release status |
|---|---|---|
| PYSEC-2026-4217 | Nautilus 1.231.0 → fsspec 2026.2.0 | Vulnerable reference-filesystem JSON uses unsandboxed Jinja rendering. Fixed fsspec is >=2026.6.0, but latest Nautilus and evaluated 1.230.0/1.229.0 pin exactly 2026.2.0. No compatible supported engine pin was found in these candidates. Release blocked. |
| GHSA-gcqx-w48m-w2h4 | @sveltejs/vite-plugin-svelte 7.3.1 → deepmerge 4.3.1 | Prototype poisoning in mergeObject; current latest deepmerge is 4.3.1, with no patched upstream version offered. Four npm findings represent this dependency chain. Release blocked. |

Reachability assessment for this increment: worker proposals accept a typed
strategy and SHA256 dataset identity, not filesystem protocol/options or template
JSON. Catalog paths are local; the source client only contacts fixed HistData
HTTPS endpoints; archive rows use decimal/CSV parsing with no evaluation. Neither
the worker nor the new importer invokes fsspec ReferenceFileSystem. This narrows
current exposure but does not remove the vulnerable installed dependency.

Deepmerge is in trusted checkout/build configuration, not the static dashboard's
application data API. Current input flows do not merge model/user-provided Vite
configuration. Untrusted local checkout code is outside that trust assumption.
This is not a vulnerability waiver, a claim the package is fixed, or permission to
add an untrusted configuration/remote-filesystem lane later.

No uv override breaks Nautilus's declared dependency constraints. Do not remove
fsspec behind the resolver, substitute an ancient engine/UI release, alter wheel
hashes, disable TLS, or exclude advisories to turn CI green. The supported next
options are a compatible upstream fix, a narrowly reviewed maintained upstream
patch/fork with full API/regression verification, or explicit owner security
review; none is declared complete here. Both dependency gates stay active and red.

Authoritative metadata rechecked: PyPI nautilus_trader/{1.231.0,1.230.0,1.229.0};
PyPI fsspec (latest 2026.9.0); npm deepmerge (latest 4.3.1); installed npm dependency
tree and fresh pip-audit 2.9.0 / npm audit reports. Raw scans remain ignored local
artifacts under reports/runtime; summarized observations are in the milestone report.
