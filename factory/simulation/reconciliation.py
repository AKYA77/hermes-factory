"""Independent event/cash/inventory checks against native engine records.

Factory Decimal equity and native USD Money balances are reported separately.
Native floating-point currency rounding is not declared equivalent to exact cash.
"""

from decimal import Decimal as D
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.identifiers import Venue
from factory.simulation.native_money import VERSION, FIXED_SCALAR, position_reference


def reconcile(engine, strategy, instrument):
    ledgers = list({id(v): v for v in strategy.order_ledgers.values()}.values())
    issues = []
    cash = fees = inventory_cost = quantity = realized = D(0)
    for ledger in ledgers:
        sign = 1 if ledger.metadata["side"] == "BUY" else -1
        inventory_cost += sign * ledger.cost
        quantity += sign * ledger.quantity
        realized += ledger.realized
        trade_cash = trade_fees = D(0)
        for fill in ledger.fills:
            value = D(fill["size"]) * D(fill["price"])
            trade_cash += value if fill["side"] == "SELL" else -value
            trade_fees += D(fill["commission"])
        cash += trade_cash
        fees += trade_fees
        if ledger.closed and trade_cash - trade_fees != ledger.realized:
            issues.append(
                {
                    "reason": "TRADE_CASH_CONSERVATION",
                    "entry_order_id": ledger.aggregate(True)["order_id"],
                    "cash_net": str(trade_cash - trade_fees),
                    "ledger_net": str(ledger.realized),
                }
            )
    if cash - fees + inventory_cost != realized:
        issues.append({"reason": "AGGREGATE_CASH_CONSERVATION"})
    if strategy.equity != D(20) + realized:
        issues.append({"reason": "FACTORY_EQUITY_CONSERVATION"})
    positions = (
        engine.cache.positions(instrument_id=instrument.id) + engine.cache.position_snapshots()
    )
    # Netting cache reopens a position ID. Lifetime first-fill identity, rather
    # than position ID alone, distinguishes its immutable closed snapshots.
    unique = {}
    for p in positions:
        if p.instrument_id == instrument.id:
            events = p.events
            unique[(str(p.id), str(events[0].trade_id))] = p
    native_fills = {}
    native_quantity = native_realized = D(0)
    native_lifetimes = {}
    for p in unique.values():
        native_lifetimes[(str(p.events[0].client_order_id), str(p.events[0].trade_id))] = p
        native_quantity += D(str(p.signed_qty))
        native_realized += p.realized_pnl.as_decimal() if p.realized_pnl else D(0)
        for event in p.events:
            key = (str(event.client_order_id), str(event.trade_id))
            value = (
                event.last_qty.as_decimal(),
                event.last_px.as_decimal(),
                event.commission.as_decimal(),
            )
            if key in native_fills:
                issues.append({"reason": "DUPLICATE_NATIVE_POSITION_FILL", "trade_id": key[1]})
            native_fills[key] = value
    factory_fills = {
        (f["order_id"], f["trade_id"]): (D(f["size"]), D(f["price"]), D(f["commission"]))
        for f in strategy.fills
    }
    if factory_fills != native_fills:
        issues.append({"reason": "NATIVE_POSITION_FILL_SET_MISMATCH"})
    if native_quantity != quantity:
        issues.append({"reason": "NATIVE_INVENTORY_MISMATCH"})
    balance = engine.cache.account_for_venue(Venue("SIM")).balance_total(USD).as_decimal()
    # A position's running Money and the account's sum of per-fill Money do
    # not have identical rounding order. Verify each against its own independent
    # reference instead of requiring those two native aggregates to agree.
    reference_status = "UNSUPPORTED_CURRENCY_OR_BUILD"
    expected_account_pnl = expected_position_pnl = D(0)
    reference_verified = False
    if instrument.quote_currency == USD and instrument.make_price(1).raw == FIXED_SCALAR:
        reference_status = "VERIFIED"
        for ledger in ledgers:
            if not ledger.fills:
                continue
            reference = position_reference(
                ledger.fills,
                currency_precision=USD.precision,
                size_precision=instrument.size_precision,
            )
            expected_account_pnl += D(reference["account_quote_pnl"])
            expected_position_pnl += D(reference["position_quote_pnl"])
            first = ledger.fills[0]
            position = native_lifetimes.get((first["order_id"], first["trade_id"]))
            actual_pnl = (
                position.realized_pnl.as_decimal()
                if position is not None and position.realized_pnl
                else D(0)
            )
            if position is None or actual_pnl != D(reference["position_quote_pnl"]):
                reference_status = "MISMATCH"
                issues.append(
                    {
                        "reason": "NATIVE_POSITION_REFERENCE_MISMATCH",
                        "first_trade_id": first["trade_id"],
                        "actual": str(actual_pnl),
                        "expected": reference["position_quote_pnl"],
                    }
                )
        if balance != D(20) + expected_account_pnl:
            reference_status = "MISMATCH"
            issues.append(
                {
                    "reason": "NATIVE_ACCOUNT_REFERENCE_MISMATCH",
                    "actual": str(balance),
                    "expected": str(D(20) + expected_account_pnl),
                }
            )
        reference_verified = reference_status == "VERIFIED"
    else:
        issues.append(
            {
                "reason": "NATIVE_MONEY_REFERENCE_UNSUPPORTED",
            }
        )
    return {
        "version": "cash-reconciliation/v2",
        "issues": issues,
        "factory_cash_flow": str(cash),
        "fees": str(fees),
        "signed_inventory": str(quantity),
        "signed_inventory_cost": str(inventory_cost),
        "factory_realized_pnl": str(realized),
        "factory_exact_equity": str(strategy.equity),
        "native_realized_pnl": str(native_realized),
        "native_balance": str(balance),
        "native_signed_inventory": str(native_quantity),
        "native_fill_count": len(native_fills),
        "native_position_lifetimes": len(unique),
        "native_minus_exact_equity": str(balance - strategy.equity),
        "native_reference_version": VERSION,
        "native_reference_status": reference_status,
        "reference_account_pnl": str(expected_account_pnl) if reference_verified else None,
        "reference_position_pnl": str(expected_position_pnl) if reference_verified else None,
        "native_position_minus_account_pnl": str(native_realized - (balance - D(20))),
        "currency_rounding_status": "REFERENCE_MISMATCH"
        if not reference_verified
        else "EXACT_MATCH"
        if balance == strategy.equity
        else "EXPLAINED_NATIVE_MONEY_POLICY",
        "scope": "Zero-commission USD-quote linear base units; cross-currency and Gold broker units remain unsupported",
    }
