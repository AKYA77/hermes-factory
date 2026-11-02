"""Order-identified fill accounting only. Nautilus remains the matching engine."""

from dataclasses import dataclass, asdict
from decimal import Decimal as D

from factory.contracts import fingerprint

EXECUTION_VERSION = "adverse-fill/v2"
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
        ):
            raise ValueError("INVALID_FILL")

    def json(self):
        value = asdict(self)
        for key in ("size", "price", "commission"):
            value[key] = str(value[key])
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
        self.realized += delta
        self.fees += fill.commission
        self._seen[key] = digest
        self.fills.append({**fill.json(), "role": order["role"]})
        return delta

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
        if self.entered and "modeled_stop_fill" in self.metadata:
            sign = 1 if self.metadata["side"] == "BUY" else -1
            modeled_risk = sum(
                (
                    (D(f["price"]) - D(self.metadata["modeled_stop_fill"])) * sign * D(f["size"])
                    for f in self.fills
                    if f["role"] == "ENTRY"
                ),
                D(0),
            )
        return {
            **self.metadata,
            "requested_quantity": str(self.requested),
            "modeled_stop_risk_for_filled_quantity": str(modeled_risk)
            if modeled_risk is not None
            else None,
            "realized_net_r": str(self.realized / modeled_risk)
            if modeled_risk and self.closed
            else None,
            "entered_quantity": str(self.entered),
            "exited_quantity": str(self.exited),
            "open_quantity": str(self.quantity),
            "entry_fill": self.aggregate(True),
            "exit_fill": self.aggregate(False) if self.closed else None,
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
            "commission": str(self.fees),
            "accounting_version": EXECUTION_VERSION,
        }


def require_execution_version(contract):
    from importlib.metadata import version

    if contract.engine_version != "1.231.0" or contract.fill_version != EXECUTION_VERSION:
        raise ValueError("unsupported engine/fill version; legacy contracts are read-only")
    if version("nautilus_trader") != contract.engine_version:
        raise ValueError("installed engine does not match execution contract")
