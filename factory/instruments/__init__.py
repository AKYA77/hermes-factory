"""No implicit broker or Gold profile: synthetic profiles are test-only."""

from decimal import Decimal as D
from factory.contracts import InstrumentSpec, SYMBOLS


def synthetic_profile(symbol):
    if symbol not in SYMBOLS:
        raise ValueError("unknown instrument")
    tick = D(".001") if symbol == "USDJPY" else D(".01") if symbol == "XAUUSD" else D(".00001")
    pip = tick * 10
    return InstrumentSpec(
        instrument=symbol,
        version="synthetic/v1",
        tick_size=tick,
        pip_size=pip,
        price_scale=int(1 / tick),
        base_currency=symbol[:3],
        quote_currency=symbol[3:],
        contract_multiplier=D(1),
        volume_step=D(".001"),
        min_volume=D(".001"),
        max_volume=D("100000"),
        margin_rate=D(".001"),
        min_stop_ticks=1,
        source="synthetic fixture; not broker metadata or verified Gold convention",
        synthetic=True,
    )
