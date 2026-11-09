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


def declared_tick_profile(symbol, price_scale, source_precision, version):
    """A profile whose declared units are measured from a real source stream.

    The synthetic profile declares minute-fixture units that genuine tick data
    does not satisfy, so profile-bound admission cannot run over acquired data.
    This derives every unit from the measured stream instead: the tick is the
    reciprocal of the observed price scale, and the precision is the observed
    source precision.

    The result is still not broker metadata. `source` records that the units were
    measured from a provider stream under a reviewed attestation, and callers
    must not present it as verified broker facts.
    """
    if symbol not in SYMBOLS:
        raise ValueError("unknown instrument")
    if price_scale < 2:
        raise ValueError("price scale must be at least 2")
    tick = D(1) / D(price_scale)
    return InstrumentSpec(
        instrument=symbol,
        version=version,
        tick_size=tick,
        pip_size=tick * 10,
        price_scale=int(price_scale),
        base_currency=symbol[:3],
        quote_currency=symbol[3:],
        contract_multiplier=D(1),
        volume_step=D(".001"),
        min_volume=D(".001"),
        max_volume=D("100000"),
        margin_rate=D(".001"),
        min_stop_ticks=1,
        source=(
            f"declared units measured from a provider stream "
            f"(price_scale={price_scale}, precision={source_precision}); "
            "not broker metadata or verified Gold convention"
        ),
        synthetic=False,
    )
