# Generic FX base-unit research profile v1

This optional, explicitly named model is for research integration. It is not a
broker's historical specification or a universal executable instrument profile.
The original $20, requested10% risk, intended1:3,2-pip spread floor and2 adverse
eligible-fill pips remain unchanged. Actual exposure can be below the requested
risk budget because this model caps the position at one base-currency unit.

Published primary facts: ISO currency identities; ordinary non-JPY FX pip0.0001,
JPY pip0.01 and fractional-pip terminology from OANDA's educational definition.
Capture and verify the actual primary documents and retain their URLs/hashes.
Those public conventions do not establish any broker's size or margin limits.

Declared model assumptions, individually cited as explicit_research_assumption:
contract_multiplier1 means quantities are base-currency units; volume_step,
minimum and maximum volume are1unit; margin_rate1 means unlevered model notional;
minimum stop is1research price-grid increment. The research price grid is the
empirically verified quote increment chosen for this model, not an inferred
broker tick. Canonical storage scale is independently verified from source data.

A generic24/5 New York session envelope may be used as a named research calendar,
with captured TZif and reviewed full gap events. This is not provider-specific
holiday or daily-maintenance certification. Do not label unresolved provider
session/gap questions resolved merely because a generic clock admits the quotes.
Separate source fidelity/research admission from full scientific validation.

Applicability dates describe the chosen research scope. A reference captured in
2026 is not asserted to have been the account specification in2025. Cite that
limitation in each dated review. No broker account, leverage offer or executable
minimum size is fabricated. Full broker feasibility remains UNKNOWN where not
supported by a dated authoritative source.

Gold is excluded from this recipe. It needs an explicit reviewed quote/base unit
and cost-equivalent convention; a source's decimal precision cannot define its
pip, contract, volume or margin. Alternative legitimate profiles get separate
immutable identities and must not be silently compared or substituted.
