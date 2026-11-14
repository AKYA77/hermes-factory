"""Instrument profile registry and integrity."""

import pytest

from factory.contracts import SYMBOLS
from factory.instruments.registry import detail, integrity, registry


def test_registry_covers_every_symbol():
    entries = registry()
    assert [entry["instrument"] for entry in entries] == list(SYMBOLS)
    assert all(entry["synthetic"] is True for entry in entries)
    assert all(len(entry["profile_hash"]) == 64 for entry in entries)
    assert len({entry["profile_hash"] for entry in entries}) == len(SYMBOLS)
    assert all(entry["source"] for entry in entries)


def test_registry_detail_and_unknown_symbol():
    entry = detail("EURUSD")
    assert entry["instrument"] == "EURUSD"
    assert entry["base_currency"] == "EUR" and entry["quote_currency"] == "USD"
    with pytest.raises(KeyError):
        detail("NOPE")


def test_integrity_recomputes_without_drift():
    report = integrity()
    assert report["profiles"] == len(SYMBOLS)
    assert report["synthetic"] == len(SYMBOLS)
    assert report["non_synthetic"] == 0
    assert report["consistent"] is True
    assert set(report["hashes"]) == set(SYMBOLS)
    assert report["model_version"]
