"""Order-identified fill accounting only. Nautilus remains the matching engine."""

from dataclasses import dataclass, asdict
from decimal import Decimal as D
from fractions import Fraction

from factory.contracts import fingerprint
from factory.monetary import decimal_amount, receipt

EXECUTION_VERSION = "adverse-fill/v4"
EXIT_ROLES = frozenset({"STOP_LOSS", "TAKE_PROFIT", "TIMEOUT", "SAFETY_CLOSE"})
TERMINAL = frozenset({"FILLED", "CANCELED", "EXPIRED", "REJECTED", "DENIED"})


@dataclass(frozen=True)
class Fill:
    order_id: str
    trade_id: str
    ts: int
    side: str
    size: D
    price: D
    commission: D = D(0)
    quote_index: int = 0
    quote_to_account: D = D(1)
    conversion_ts: int | None = None
    conversion_source: str = "USD_IDENTITY"
    conversion_bid: D | None = None
    conversion_ask: D | None = None

    def __post_init__(self):
        if (
            not self.order_id
            or not self.trade_id
            or self.side not in ("BUY", "SELL")
            or not self.size.is_finite()
            or self.size <= 0
            or not self.price.is_finite()
            or self.price <= 0
            or not self.commission.is_finite()
            or self.ts < 0
            or self.quote_index < 0
            or not self.quote_to_account.is_finite()
            or self.quote_to_account <= 0
            or (self.conversion_ts is not None and self.conversion_ts != self.ts)
            or not self.conversion_source
            or ((self.conversion_bid is None) != (self.conversion_ask is None))
            or (
                self.conversion_bid is not None
                and (
                    not self.conversion_bid.is_finite()
                    or not self.conversion_ask.is_finite()
                    or self.conversion_bid <= 0
                    or self.conversion_ask < self.conversion_bid
                )
            )
        ):
            raise ValueError("INVALID_FILL")

    def json(self):
        value = asdict(self)
        for key in ("size", "price", "commission", "quote_to_account"):
            value[key] = str(value[key])
        for key in ("conversion_bid", "conversion_ask"):
            value[key] = str(value[key]) if value[key] is not None else None
        return value


class TradeLedger:
    def __init__(self, metadata, requested_quantity):
        self.metadata = metadata
        self.requested = D(requested_quantity)
        if self.requested <= 0:
            raise ValueError("INVALID_QUANTITY")
        self.orders = {}
        self.fills = []
        self._seen = {}
        self.entered = self.exited = self.cost = self.realized = self.fees = D(0)
        self.realized_quote = D(0)
        self.account_realized_exact = Fraction(0)
        self.last_account_delta_exact = Fraction(0)
        self.events = []

    def register(self, order_id, role):
        if role not in EXIT_ROLES | {"ENTRY"} or not order_id:
            raise ValueError("INVALID_ORDER_ROLE")
        if order_id in self.orders:
            if self.orders[order_id]["role"] != role:
                raise ValueError("ORDER_ID_REUSED")
            return
        if role == "ENTRY" and any(o["role"] == "ENTRY" for o in self.orders.values()):
            raise ValueError("MULTIPLE_ENTRY_ORDERS")
        self.orders[order_id] = {"role": role, "terminal": None}

    def terminal(self, order_id, status):
        if order_id not in self.orders or status not in TERMINAL:
            raise ValueError("UNKNOWN_ORDER_OR_STATUS")
        prior = self.orders[order_id]["terminal"]
        if prior and prior != status:
            raise ValueError("CONFLICTING_ORDER_TERMINAL_STATE")
        self.orders[order_id]["terminal"] = status
        self.events.append({"order_id": order_id, "status": status})

    @property
    def quantity(self):
        return self.entered - self.exited

    @property
    def entry_terminal(self):
        return any(o["role"] == "ENTRY" and o["terminal"] for o in self.orders.values())

    @property
    def closed(self):
        return self.entry_terminal and self.entered > 0 and self.quantity == 0

    def apply(self, fill):
        key = (fill.order_id, fill.trade_id)
        digest = fingerprint(fill.json())
        if key in self._seen:
            if self._seen[key] != digest:
                raise ValueError("CONFLICTING_DUPLICATE_FILL")
            return D(0)
        order = self.orders.get(fill.order_id)
        if order is None:
            raise ValueError("UNKNOWN_FILL_ORDER")
        if order["terminal"]:
            raise ValueError("FILL_AFTER_TERMINAL")
        entry = order["role"] == "ENTRY"
        expected = (
            self.metadata["side"]
            if entry
            else ("SELL" if self.metadata["side"] == "BUY" else "BUY")
        )
        if fill.side != expected:
            raise ValueError("FILL_SIDE_MISMATCH")
        if self.fills and (fill.ts, fill.quote_index) < (
            self.fills[-1]["ts"],
            self.fills[-1]["quote_index"],
        ):
            raise ValueError("OUT_OF_ORDER_FILL")
        if entry and self.entered + fill.size > self.requested:
            raise ValueError("ENTRY_OVERFILL")
        if not entry and fill.size > self.quantity:
            raise ValueError("EXIT_OVERFILL")
        delta = -fill.commission
        if entry:
            self.cost += fill.size * fill.price
            self.entered += fill.size
        else:
            basis = self.cost / self.quantity
            delta += (
                (fill.price - basis) * fill.size * (1 if self.metadata["side"] == "BUY" else -1)
            )
            if fill.size == self.quantity:
                # Reconcile the last inventory cash cost without leaving a
                # rounding residue from intermediate average-cost divisions.
                delta = (fill.price * fill.size - self.cost) * (
                    1 if self.metadata["side"] == "BUY" else -1
                ) - fill.commission
                self.cost = D(0)
            else:
                self.cost -= basis * fill.size
            self.exited += fill.size
        self.realized_quote += delta
        # Sum finite Decimal inputs as rational numbers so associativity cannot
        # create unexplained currency residuals. Decimal is a reporting boundary.
        self.last_account_delta_exact = Fraction(delta) * Fraction(fill.quote_to_account)
        self.account_realized_exact += self.last_account_delta_exact
        account_delta = decimal_amount(self.last_account_delta_exact)
        self.realized = decimal_amount(self.account_realized_exact)
        self.fees += fill.commission
        self._seen[key] = digest
        self.fills.append({**fill.json(), "role": order["role"]})
        return account_delta

    def aggregate(self, entry):
        fills = [f for f in self.fills if (f["role"] == "ENTRY") == entry]
        if not fills:
            return None
        quantity = sum((D(f["size"]) for f in fills), D(0))
        price = sum((D(f["size"]) * D(f["price"]) for f in fills), D(0)) / quantity
        ids = sorted({f["order_id"] for f in fills})
        return {
            "order_id": ids[0] if len(ids) == 1 else None,
            "order_ids": ids,
            "trade_ids": [f["trade_id"] for f in fills],
            "ts": fills[0]["ts"] if entry else fills[-1]["ts"],
            "quote_index": fills[0]["quote_index"] if entry else fills[-1]["quote_index"],
            "price": str(price),
            "size": str(quantity),
            "side": fills[0]["side"],
            "aggregation": "quantity_weighted",
            "fill_count": len(fills),
        }

    def snapshot(self):
        reasons = sorted({f["role"] for f in self.fills if f["role"] != "ENTRY"})
        modeled_risk = None
        modeled_risk_exact = None
        if self.entered and "modeled_stop_fill" in self.metadata:
            sign = 1 if self.metadata["side"] == "BUY" else -1
            modeled_risk_exact = Fraction(D(self.metadata.get("risk_conversion_rate", "1"))) * sum(
                (
                    Fraction(D(f["price"]) - D(self.metadata["modeled_stop_fill"]))
                    * sign
                    * Fraction(D(f["size"]))
                    for f in self.fills
                    if f["role"] == "ENTRY"
                ),
                Fraction(0),
            )
            modeled_risk = decimal_amount(modeled_risk_exact)
        return {
            **self.metadata,
            "requested_quantity": str(self.requested),
            "modeled_stop_risk_for_filled_quantity": str(modeled_risk)
            if modeled_risk is not None
            else None,
            "modeled_stop_risk_exact": receipt(modeled_risk_exact)
            if modeled_risk_exact is not None
            else None,
            "realized_net_r": str(decimal_amount(self.account_realized_exact / modeled_risk_exact))
            if modeled_risk and self.closed
            else None,
            "entered_quantity": str(self.entered),
            "exited_quantity": str(self.exited),
            "open_quantity": str(self.quantity),
            "entry_fill": self.aggregate(True),
            "exit_fill": self.aggregate(False) if self.closed else None,
            "execution_fills": list(self.fills),
            "entry_fills": [f for f in self.fills if f["role"] == "ENTRY"],
            "exit_fills": [f for f in self.fills if f["role"] != "ENTRY"],
            "exit_reason": reasons[0]
            if len(reasons) == 1 and self.closed
            else "MIXED"
            if self.closed
            else None,
            "exit_reasons": reasons,
            "closed": self.closed,
            "order_states": {k: dict(v) for k, v in self.orders.items()},
            "order_events": list(self.events),
            "pnl": str(self.realized),
            "pnl_exact": receipt(self.account_realized_exact),
            "quote_currency_pnl": str(self.realized_quote),
            "commission": str(self.fees),
            "accounting_version": EXECUTION_VERSION,
        }


def require_execution_version(contract):
    from importlib.metadata import version
    from factory.provenance import source_identity

    if contract.engine_version != "1.231.0" or contract.fill_version != EXECUTION_VERSION:
        raise ValueError("unsupported engine/fill version; legacy contracts are read-only")
    if version("nautilus_trader") != contract.engine_version:
        raise ValueError("installed engine does not match execution contract")
    context = source_identity()
    actual = context["git_commit"] + "@source-sha256:" + context["source_sha256"]
    if contract.code_revision != actual:
        raise ValueError("execution source revision mismatch")
    return {**context, "engine_version": version("nautilus_trader")}
