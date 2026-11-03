"""Independent event/cash/inventory checks against native engine records.

Factory Decimal equity and native USD Money balances are reported separately.
Native floating-point currency rounding is not declared equivalent to exact cash.
"""

from decimal import Decimal as D
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.identifiers import Venue


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
    for p in unique.values():
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
    if balance != D(20) + native_realized:
        issues.append(
            {
                "reason": "NATIVE_BALANCE_POSITION_MISMATCH",
                "balance": str(balance),
                "positions_imply": str(D(20) + native_realized),
            }
        )
    return {
        "version": "cash-reconciliation/v1",
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
        "currency_rounding_status": "EXACT_MATCH"
        if balance == strategy.equity
        else "DIFFERENCE_REQUIRES_POLICY",
        "scope": "USD quote profiles only; no assertion of cross-currency or Gold correctness",
    }
