"""Exact USD-quote valuation of actual fills; no order matching or invented fills.

Full-stream drawdown uses every quote and actual fill transition. The bounded
curve is a display envelope only, never an input to research or execution.
"""

from decimal import Decimal as D
from factory.simulation.pricing import effective_quotes


class Envelope:
    def __init__(self, max_points):
        if not 8 <= max_points <= 4096:
            raise ValueError("invalid equity display budget")
        self.limit = max_points // 4
        self.width = 1
        self.bins = []
        self.ordinal = 0

    def add(self, point):
        point = {**point, "observation": self.ordinal}
        bucket = self.ordinal // self.width
        self.ordinal += 1
        if not self.bins or self.bins[-1]["bucket"] != bucket:
            self.bins.append(
                {"bucket": bucket, "first": point, "last": point, "min": point, "max": point}
            )
        else:
            item = self.bins[-1]
            item["last"] = point
            if D(point["equity"]) < D(item["min"]["equity"]):
                item["min"] = point
            if D(point["equity"]) > D(item["max"]["equity"]):
                item["max"] = point
        if len(self.bins) > self.limit:
            self.width *= 2
            merged = []
            for item in self.bins:
                bucket = item["first"]["observation"] // self.width
                if merged and merged[-1]["bucket"] == bucket:
                    previous = merged[-1]
                    previous["last"] = item["last"]
                    if D(item["min"]["equity"]) < D(previous["min"]["equity"]):
                        previous["min"] = item["min"]
                    if D(item["max"]["equity"]) > D(previous["max"]["equity"]):
                        previous["max"] = item["max"]
                else:
                    merged.append({**item, "bucket": bucket})
            self.bins = merged

    def points(self):
        points = {
            p["observation"]: p
            for item in self.bins
            for p in (item["first"], item["min"], item["max"], item["last"])
        }
        return [points[key] for key in sorted(points)]


def equity_summary(rows, scale, profile, result, conservative, *, max_points=256):
    if profile.quote_currency != "USD" or profile.contract_multiplier != 1:
        return {
            "version": "marked-equity/v1",
            "status": "UNKNOWN_CONVERSION_OR_UNITS",
            "curve": [],
            "scope": "requires a verified dated account-currency valuation policy",
        }
    cash = peak = D(20)
    inventory = D(0)
    max_dd = D(0)
    minimum = D(20)
    insolvent = False
    fills = iter(result["fills"])
    current = next(fills, None)
    seen = set()
    envelope = Envelope(max_points)
    count = 0
    previous = None
    last_mark = D(20)

    def observe(row, bid, ask, index, phase):
        nonlocal peak, max_dd, minimum, insolvent, last_mark
        marked = cash + inventory * (bid if inventory >= 0 else ask)
        peak = max(peak, marked)
        max_dd = max(max_dd, (peak - marked) / peak)
        minimum = min(minimum, marked)
        insolvent = insolvent or marked <= 0
        last_mark = marked
        envelope.add(
            {
                "ts": row[0],
                "quote_index": index,
                "source_record_order": row[3],
                "equity": str(marked),
                "phase": phase,
            }
        )

    for index, row in enumerate(rows):
        ts, bid_int, ask_int = row[:3]
        if bid_int <= 0 or ask_int < bid_int or (previous is not None and ts < previous):
            raise ValueError("invalid equity quote chronology/prices")
        previous = ts
        bid, ask = effective_quotes(D(bid_int) / scale, D(ask_int) / scale, profile, conservative)
        observe(row, bid, ask, index, "quote_before_fills")
        while current is not None and current["quote_index"] <= index:
            if current["quote_index"] != index or current["ts"] != ts:
                raise ValueError("equity fill/source ordering mismatch")
            key = (current["order_id"], current["trade_id"])
            if key in seen:
                raise ValueError("duplicate equity fill identity")
            seen.add(key)
            size, price, fee = D(current["size"]), D(current["price"]), D(current["commission"])
            if size <= 0 or price <= 0 or current["side"] not in ("BUY", "SELL"):
                raise ValueError("invalid equity fill")
            sign = D(1) if current["side"] == "BUY" else D(-1)
            cash -= sign * size * price + fee
            inventory += sign * size
            observe(row, bid, ask, index, "after_fill")
            current = next(fills, None)
        count += 1
    if not count or current is not None:
        raise ValueError("equity source missing for actual fills")
    if not inventory and cash != D(result["ending_equity"]):
        raise ValueError("MARKED_EQUITY_CASH_CONSERVATION")
    opened = result.get("open_trade")
    expected_inventory = (
        D(opened["open_quantity"]) * (1 if opened["side"] == "BUY" else -1) if opened else D(0)
    )
    if inventory != expected_inventory:
        raise ValueError("MARKED_EQUITY_INVENTORY_CONSERVATION")
    return {
        "version": "marked-equity/v1",
        "status": "EXACT_USD_QUOTE_VALUATION",
        "ending_marked_equity": str(last_mark),
        "realized_balance_reference": result["ending_equity"],
        "unrealized_pnl": str(last_mark - D(result["ending_equity"])),
        "notional_cash_flow_balance": str(cash),
        "signed_open_quantity": str(inventory),
        "peak_marked_equity": str(peak),
        "minimum_marked_equity": str(minimum),
        "max_mark_to_market_drawdown": str(max_dd),
        "insolvent_at_any_observation": insolvent,
        "quote_observations": count,
        "fill_observations": len(seen),
        "curve": envelope.points(),
        "curve_policy": "bounded chronological min/max display envelope; stats use every quote/fill",
        "curve_is_execution_input": False,
        "mark_policy": "effective liquidation-side bid/ask; adverse slippage booked on actual fills only",
        "cash_interpretation": "notional cash plus executable-side open inventory equals equity; not native free margin",
    }
