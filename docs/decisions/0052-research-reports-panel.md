# ADR0052 — Research reports dashboard panel

Status: implemented software scope; full scientific acceptance open.

## Problem

ADR0043 through ADR0051 added reports and registries, but the dashboard exposed
only cohorts, comparability, discovery, source quality and input reviews. The new
aggregates were reachable through the API and CLI but not through the operator
interface.

## Decision

`apps/dashboard/src/lib/ResearchReportsPanel.svelte` surfaces, under the Research
view:

- the global selection funnel (ADR0046);
- annual and pooled reporting (ADR0045);
- independent qualified ranking (ADR0049);
- storage inventory (ADR0050);
- instrument profiles (ADR0051);
- committed data sources (ADR0050).

The panel loads profiles and sources on mount, fetches storage once, and fetches
each aggregate on demand. Every report action requires the operator to name an
authorizer and tick the descriptive-use attestation; the buttons stay disabled
until both are supplied.

## Safeguards

- The panel presents descriptive aggregates only.
- No report qualifies, ranks or promotes a strategy.
- Storage and source figures are reported, never repaired.
- Profile entries carry their synthetic flag and content hash.

svelte-check reports 0 errors and 0 warnings; the production build succeeds.

Evidence: docs/milestone-historical-screen-cohorts.md.
