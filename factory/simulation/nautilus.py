"""Thin supported fill-book extension. Nautilus owns orders, fills and accounts."""

from decimal import Decimal as D

from nautilus_trader.backtest.models import FillModel
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.enums import BookType, OrderSide, OrderType


class AdverseFillModel(FillModel):
    def __init__(self, profile, conservative):
        super().__init__(prob_fill_on_limit=1.0, prob_slippage=0.0, random_seed=0)
        self.profile = profile
        self.conservative = conservative
        self.trace = []

    def get_orderbook_for_fill_simulation(self, instrument, order, best_bid, best_ask):
        slip = (
            2 * self.profile.pip_size
            if self.conservative and order.order_type in (OrderType.MARKET, OrderType.STOP_MARKET)
            else D(0)
        )
        # Called only when the engine has established order eligibility. Limit liquidity
        # stays on the real effective quote and the engine enforces the order limit.
        bid = best_bid.as_decimal() - slip
        ask = best_ask.as_decimal() + slip
        book = OrderBook(instrument.id, BookType.L2_MBP)
        quantity = instrument.make_qty(max(D("1000000"), order.quantity.as_decimal()))
        book.add(BookOrder(OrderSide.BUY, instrument.make_price(bid), quantity, 1), 0, 0)
        book.add(BookOrder(OrderSide.SELL, instrument.make_price(ask), quantity, 2), 0, 0)
        self.trace.append(
            {
                "order_id": str(order.client_order_id),
                "order_type": str(order.order_type),
                "side": str(order.side),
                "bid": str(best_bid),
                "ask": str(best_ask),
                "slippage": str(slip),
                "model": "adverse-fill/v1",
            }
        )
        return book
