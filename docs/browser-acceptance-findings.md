# Browser acceptance: harness defects found and fixed

Status: all six dashboard browser-acceptance smokes now pass end to end against
real Chromium on this host. Each had a distinct defect that made it impossible
to run, and none was covered by a test or CI, so none had ever been verified.

The smokes drive a real Chromium through the served dashboard with an
authenticated operator token. They are the only automated proof that the
dashboard's workflows work in a browser rather than only through the API.

## Defects found

| # | Defect | Consequence |
|---|---|---|
| 1 | Five of six smokes hardcoded `/usr/bin/chromium`, which does not exist on this host | The smokes could never launch a browser |
| 2 | `serve` does not start a coordinator, and no runner started one | Any workflow needing a job to actually run (freeze, native audit, export) silently never completed |
| 3 | The historical smoke polled at 250 ms against a limiter allowing 120 requests/60 s per token | Every run tripped `429` during the audit poll |
| 4 | The discovery smoke used a page-global `getByLabel('Authorized by')` while two panels expose that field | Strict-mode violation, ambiguous locator |
| 5 | `reviewed-inputs-browser-fixture.py` accepted `--state` but hardcoded its path | A caller passing a fresh isolated directory was silently ignored, then the fixture refused because its hardcoded directory existed |
| 6 | `reviewed-inputs-browser-smoke.cjs` hardcoded both the state path and the URL, ignoring `FACTORY_BROWSER_STATE`/`FACTORY_BROWSER_URL` | The wrapper's isolation was bypassed |
| 7 | The revocation step spawned `.venv/bin/python` inheriting an ambient `PYTHONPATH` that points at Python 3.14 site-packages | The venv's Python 3.12 could not import `pydantic_core`, so revocation always failed |
| 8 | The wrapper pre-created the state directory, but some fixtures require it to be absent | Those fixtures refused to run |

## Fixes

- `scripts/lib/chromium-path.cjs` resolves a Chromium executable: explicit
  `FACTORY_CHROMIUM`, then known tool/system paths, then Playwright's bundled
  browser, failing loudly if none exists. All six smokes use it.
- `scripts/run-browser-smoke.sh` starts the dashboard **and** a coordinator
  against one isolated TEST_ONLY state, waits for the API, runs the smoke, and
  tears both down. It does not pre-create the state directory, leaving that
  decision to the fixture.
- The historical smoke polls at 750 ms (80/min, inside the 120/60 s budget) and
  backs off on `429` instead of failing.
- The discovery smoke scopes its `Authorized by` locator to the discovery panel.
- The reviewed-inputs fixture honours `--state`; its smoke honours both env vars.
- The revocation spawn sanitizes `PYTHONPATH`.

## Verified result

All six pass with zero page errors and no mobile overflow:

- `discovery-browser` — authenticated registration, pause preserved, region
  created only after resume, exact export.
- `historical-screen-cohort-browser` — cohort frozen before outcomes, fenced
  native feedback (`native_observed = 1`, `approximate_pruning = false`),
  exact-byte export, `429`-free.
- `reviewed-inputs-browser` — registry summaries, exact-byte export, revoked
  dependency refusal, mobile layout.
- `screen-cohort-browser` — supervised native feedback, prospective false
  negative, exact export.
- `screen-fallback-browser` — native fault injection, disabled alert, pause
  preserved.
- `validation-browser` — live validation list, exact nanosecond download,
  protected window state, typed UTC prospective registration, disable stages.

## Attestation literals

Every report and action endpoint pins its own attestation literal. A panel that
sends a different string fails at runtime with `422` and surfaces only as an alert
after the user clicks — which is exactly how the Research reports panel shipped
broken: one generic attestation for three endpoints that each pin their own.

`scripts/check-dashboard-attestations.py` compares the literals declared in
`apps/dashboard/src/lib/*.svelte` against every attestation literal defined under
`factory/`, catching the mismatch before it reaches a browser. It reports backend
literals with no panel separately, since those endpoints are reached through the
CLI or API rather than the dashboard.

Current result: **7 panel literals, 19 backend literals, 0 unmatched.**

`tests/integration/test_dashboard_attestations.py` runs the check and also proves
it fails on a deliberately mismatched panel, so it cannot pass vacuously.

Note that the project's Ruff scope is `factory apps tests`; `scripts/` is not
linted, so the check script is excluded from that gate by design.

## The dashboard smoke was silently broken

The section above recorded the hardcoded-Chromium defect as fixed in five
smokes. `scripts/dashboard-smoke.cjs` was a sixth and was missed: it still
launched `executablePath:'/usr/bin/chromium'`, which does not exist on this host,
so the smoke could never run. Because the wrapper reports a non-zero exit and the
dashboard smoke produced no receipt, the failure was invisible in the artifact
record — only running it directly exposed it. It now uses the same
`lib/chromium-path.cjs` resolver as the other seven.

A second defect sat immediately next to it. `reviewed-inputs-browser-smoke.cjs`
did launch through the resolver, but wrote `browser: 'Chromium /usr/bin/chromium'`
into its receipt. The launch was correct and the evidence was false — the receipt
now records the actual browser version, captured before `browser.close()`.

All eight smokes now pass: the six listed above, the dashboard smoke, and the
Source quality smoke over real acquired archives.

## Scope

Every one of these runs against **generated TEST_ONLY fixtures**, not market
data — with one exception: the Source quality smoke runs over genuine acquired
partitions, but its receipts still carry `synthetic=false` only for the source
and `historical_admission=false` for the conclusion. They prove the dashboard's
controls, authentication, exact-byte export and mobile layout work in a real
browser. They do not validate market behaviour, and they do not make
`SOFTWARE_VERIFIED`, `DATA_READY` or `OPERATION_READY` true.
