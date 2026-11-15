# Execution v3: explicit IOC market remainders

Status: tested software correction; C3 and release readiness remain incomplete.
The owner requested correction of partial fills, cancellation and conservative
execution. The blueprint's two-pip eligible adjustment, minimum spread, intended
1:3 distances and risk calculation are unchanged.

The pinned Nautilus engine extrapolates an exhausted L1 GTC market remainder one
extra tick. A fresh supported-API probe found that liquidity_consumption=True
also leaves this behavior for market orders. Do not enable that option as a fix
or silently rewrite actual prices. The regression fixtures preserve the original
GTC behavior explicitly as a read-only reference.

New execution contracts use adverse-fill/v3. Market entries, stop-market children
and reduce-only market exits explicitly use IOC. Unfilled remainders cancel;
filled quantities and cancellation events remain in the ledger. Lost protection
uses the existing identified safety-close path, using real engine events and
quotes. Take-profit limits remain GTC and may not fill through their limit.
This is not fill-or-kill: genuine partial exposure remains visible. An unfinished
close may remain open when no executable quote follows. No synthetic close is
inserted. The native engine still owns all execution.

Finite-book long and short entry/stop fixtures now verify exact eligible prices,
actual cancellation, flat final inventory where liquidity is available, original
3R intent, and distinct STOP_LOSS versus SAFETY_CLOSE identities. These fixtures
are software tests; historical L1 data do not establish real order-book depth.
The default transparent unlimited-liquidity scenario is unchanged in that regard.

Private _legacy_gtc_reference replay is for regression comparison only. The
experiment completion boundary rejects its artifacts. Existing v1/v2 results
remain readable but cannot run under v3 or share its official comparison group.

Verification: bash scripts/verify.sh, 190 passed, zero failures/skips, 182
third-party warnings, 66.77 seconds; Ruff and dashboard check/build passed.
Log: /tmp/hermes-mandate-ioc-v3-verify.log. This does not complete currency,
Gold contract-unit, native rounding, source-profile or target-host gates.
