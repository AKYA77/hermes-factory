"""Data source registry and storage inventory."""

import pytest

from factory.data.sources import SourceRegistry
from factory.operations.fixtures import seed


def test_source_registry_lists_and_inventories(tmp_path):
    payload = seed(tmp_path, 240)
    identity = payload["contract"]["dataset_hash"]
    registry = SourceRegistry(tmp_path / "catalog")
    sources = registry.list()
    assert len(sources) == 1
    assert sources[0]["instrument"] == "EURUSD"
    assert sources[0]["dataset_hash"] == identity
    assert sources[0]["fidelity"] == "SYNTHETIC"
    assert sources[0]["rows"] == 240
    assert sources[0]["bytes"] > 0
    storage = registry.storage()
    assert storage["partitions"] == 1
    assert storage["rows"] == 240
    assert storage["by_instrument"]["EURUSD"]["rows"] == 240
    assert registry.detail(identity)["dataset_hash"] == identity
    with pytest.raises(KeyError):
        registry.detail("0" * 64)


def test_refresh_verifies_partition_digests(tmp_path):
    payload = seed(tmp_path, 240)
    identity = payload["contract"]["dataset_hash"]
    registry = SourceRegistry(tmp_path / "catalog")
    receipt = registry.refresh()
    assert receipt["status"] == "REFRESH_COMPLETE"
    assert receipt["consistent"] is True
    assert receipt["verified"] == 1
    assert receipt["mismatched"] == []
    parquet = tmp_path / "catalog" / identity / "quotes.parquet"
    parquet.write_bytes(b"corrupt")
    receipt = registry.refresh()
    assert receipt["consistent"] is False
    assert receipt["mismatched"][0]["dataset_hash"] == identity
