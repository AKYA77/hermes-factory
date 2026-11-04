"""Versioned immutable domain contracts and deterministic identities."""

from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "XAUUSD")
TIMEFRAMES = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}


def canonical(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("nonfinite decimal")
        parts = value.as_tuple()
        if len(parts.digits) + abs(parts.exponent) > 16384:
            raise ValueError("CANONICAL_DECIMAL_RESOURCE_LIMIT")
        # Decimal.normalize() uses the active arithmetic context and can round
        # distinct inputs to the same fingerprint. Formatting is exact; remove
        # only insignificant fractional zeros, without numerical operations.
        encoded = format(value, "f")
        return encoded.rstrip("0").rstrip(".") if "." in encoded else encoded
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    return value


def serialize(value):
    return json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(serialize(value).encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Signal(Contract):
    operator: Literal["mean_reversion", "momentum", "breakout"]
    lookback: int = Field(ge=2, le=500)
    threshold: Decimal = Field(gt=0, le=20)
    version: Literal["1"] = "1"


class StrategySpec(Contract):
    schema_version: Literal["strategy/v1"] = "strategy/v1"
    instrument: str
    timeframe: str
    signal: Signal
    confirmations: tuple[str, ...] = ()
    stop_ticks: int = Field(gt=0, le=1000000)
    target_rr: Literal["3"] = "3"
    max_hold_seconds: int = Field(default=86400, gt=0, le=86400)
    direction: Literal["both", "long", "short"] = "both"
    semantic_version: Literal["1"] = "1"

    @model_validator(mode="after")
    def valid(self):
        if self.instrument not in SYMBOLS or self.timeframe not in TIMEFRAMES:
            raise ValueError("unsupported instrument/timeframe")
        if len(set(self.confirmations)) != len(self.confirmations):
            raise ValueError("duplicate confirmation")
        if any(
            t not in TIMEFRAMES or TIMEFRAMES[t] <= TIMEFRAMES[self.timeframe]
            for t in self.confirmations
        ):
            raise ValueError("confirmations must be higher timeframes")
        return self

    @property
    def strategy_hash(self):
        return fingerprint(self)


class InstrumentSpec(Contract):
    instrument: str
    version: str
    tick_size: Decimal = Field(gt=0)
    pip_size: Decimal = Field(gt=0)
    price_scale: int = Field(gt=0)
    base_currency: str
    quote_currency: str
    contract_multiplier: Decimal = Field(gt=0)
    volume_step: Decimal = Field(gt=0)
    min_volume: Decimal = Field(gt=0)
    max_volume: Decimal = Field(gt=0)
    margin_rate: Decimal = Field(gt=0, le=1)
    min_stop_ticks: int = Field(ge=1)
    source: str
    synthetic: bool

    @model_validator(mode="after")
    def units(self):
        if self.instrument not in SYMBOLS or self.min_volume > self.max_volume:
            raise ValueError("invalid instrument specification")
        if self.base_currency != self.instrument[:3] or self.quote_currency != self.instrument[3:]:
            raise ValueError("instrument currency identity mismatch")
        if (self.tick_size * self.price_scale) % 1 or self.pip_size % self.tick_size:
            raise ValueError("ambiguous tick/pip units")
        if not self.source.strip():
            raise ValueError("UNKNOWN_SPEC")
        return self


class Window(Contract):
    start_ns: int = Field(ge=0)
    end_ns: int = Field(gt=0)
    role: Literal[
        "train_only", "selection_oos", "final_holdout_unseen", "paper_forward", "report_only"
    ]

    @model_validator(mode="after")
    def ordered(self):
        if self.start_ns >= self.end_ns:
            raise ValueError("empty/reversed window")
        return self


class ExperimentContract(Contract):
    schema_version: Literal["experiment/v1"] = "experiment/v1"
    strategy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    instrument_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    engine_version: str
    code_revision: str
    fill_version: str
    evaluation_policy: str
    scenario: Literal["historical-reference/v1", "historical-pessimistic/v1"]
    windows: tuple[Window, ...]
    seed: int = Field(ge=0)
    initial_equity: Decimal = Decimal("20")
    risk_fraction: Decimal = Decimal(".10")
    overlap_policy: Literal["one-position"] = "one-position"

    @model_validator(mode="after")
    def invariants(self):
        if self.initial_equity != 20 or self.risk_fraction != Decimal(".10"):
            raise ValueError("new risk profile requires approved contract version")
        if not self.windows:
            raise ValueError("evaluation windows required")
        ordered = sorted(self.windows, key=lambda w: w.start_ns)
        if any(a.end_ns > b.start_ns for a, b in zip(ordered, ordered[1:])):
            raise ValueError("overlapping evaluation windows")
        return self

    @property
    def experiment_hash(self):
        return fingerprint(self)
