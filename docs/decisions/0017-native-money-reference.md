# Independent reference for native Money rounding

Status: tested component, not complete C3 or release acceptance.
Authority: blueprint section 9 and owner mandate to reconcile native accounting.

The exact Decimal research ledger remains authoritative for its declared research
scenario. Native cash is reported separately, with the pinned engine's binary64
and currency-precision policy. Matching, order events and fills are unchanged.

Source inspection of Nautilus 1.231.0 shows two distinct native paths. Margin
account P&L rounds each close delta to quote-currency Money before applying it.
Position P&L adds each unrounded binary64 delta to its previous rounded Money,
then constructs a new Money. Both use fixed integer-to-binary64 conversion and
binary64 average entry. Money(value, currency) rounds binary64 scaled values to
nearest with ties away from zero; Money.from_str uses another policy and is not
an interchangeable reference for that constructor.

native_money.py implements a small independent accounting reference without
calling native matching, Money or Position. Reconciliation checks native account
and each native position lifetime against their respective references. A delta
between exact research equity and correctly explained native rounding is labeled
EXPLAINED_NATIVE_MONEY_POLICY. Reference mismatches remain integrity errors. No
epsilon or unexplained rounding discrepancy is accepted. A different fixed-point
build/currency/commission scope is explicitly unsupported.

Native goldens verify positive/negative boundaries against actual Money for
66,003 constructor values in USD/JPY/CHF, and quote-P&L partial entry/exit paths
for all eight synthetic instruments, both sides, 20 seeded position lifetimes
each (320 lifetimes/1,600 fills). A deliberately signed .03-profit/-.015-loss
example reproduces actual native position P&L .02 versus account quote P&L .01.
Those are legitimate different rounding orders; the former universal equality
assertion would reject the native result incorrectly. These are software fixtures,
not historical trading evidence or broker specification verification.

Current production reconciliation scope is zero-commission USD quote, linear
base units and the pinned high-precision build. Dated USDJPY/USDCHF/USDCAD
conversion, Gold broker lots, verified profile admission and full monetary
release acceptance remain unfinished. A separate synthetic native gap probe
confirmed that a protective exit sees the previous main cached quote, giving
19.80 USD instead of current-quote 19.75 USD in that constructed probe. An
ordered duplicate conversion-context quote corrects the probe through supported
engine APIs. That context adapter is not yet integrated or accepted for research.
Probe JSON is retained in reports/runtime; no native package was patched.
