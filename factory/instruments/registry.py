"""Instrument profile registry and integrity.

Lists every known instrument profile with its provenance and content hash. A
profile is a declared model constraint, never broker metadata or a validated
trading specification.
"""

from factory.contracts import SYMBOLS, fingerprint
from factory.instruments import synthetic_profile
from factory.instruments.research_profiles import MODEL_VERSION


def _entry(spec):
    return {
        "instrument": spec.instrument,
        "version": spec.version,
        "synthetic": spec.synthetic,
        "source": spec.source,
        "tick_size": str(spec.tick_size),
        "pip_size": str(spec.pip_size),
        "price_scale": spec.price_scale,
        "base_currency": spec.base_currency,
        "quote_currency": spec.quote_currency,
        "contract_multiplier": str(spec.contract_multiplier),
        "volume_step": str(spec.volume_step),
        "min_volume": str(spec.min_volume),
        "max_volume": str(spec.max_volume),
        "margin_rate": str(spec.margin_rate),
        "min_stop_ticks": spec.min_stop_ticks,
        "profile_hash": fingerprint(spec.model_dump(mode="json")),
    }


def registry():
    return [_entry(synthetic_profile(symbol)) for symbol in SYMBOLS]


def detail(symbol):
    if symbol not in SYMBOLS:
        raise KeyError(symbol)
    return _entry(synthetic_profile(symbol))


def integrity():
    """Recompute every profile hash and report drift."""
    entries = registry()
    return {
        "model_version": MODEL_VERSION,
        "profiles": len(entries),
        "synthetic": sum(1 for entry in entries if entry["synthetic"]),
        "non_synthetic": sum(1 for entry in entries if not entry["synthetic"]),
        "hashes": {entry["instrument"]: entry["profile_hash"] for entry in entries},
        "consistent": all(
            entry["profile_hash"] == detail(entry["instrument"])["profile_hash"]
            for entry in entries
        ),
        "limitations": [
            "Synthetic profiles are test-only and not broker metadata",
            "Gold requires its own reviewed cost-equivalent/units definition",
            "Choosing this model does not certify historical broker feasibility",
        ],
    }
