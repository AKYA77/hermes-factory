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


def test_refresh_verifies_a_view_through_its_leaves(tmp_path):
    """A composed view has no parquet of its own and must not read as missing.

    Reporting a view as a missing leaf made refresh claim inconsistency on a
    fully consistent catalog.
    """
    import json

    payload = seed(tmp_path, 240)
    identity = payload["contract"]["dataset_hash"]
    catalog = tmp_path / "catalog"
    registry = SourceRegistry(catalog)
    leaf_manifest = json.loads((catalog / identity / "manifest.json").read_text())
    parquet = catalog / identity / "quotes.parquet"
    view_identity = "v" * 64
    (catalog / view_identity).mkdir()
    (catalog / view_identity / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_hash": view_identity,
                "schema_version": "data/view-v1",
                "instrument": leaf_manifest["instrument"],
                "rows": leaf_manifest["rows"],
                "parts": [
                    {
                        "dataset_hash": identity,
                        "parquet_sha256": leaf_manifest["parquet_sha256"],
                        "rows": leaf_manifest["rows"],
                        "first_ns": leaf_manifest["first_ns"],
                        "last_ns": leaf_manifest["latest_verified_ns"],
                    }
                ],
            }
        )
    )
    receipt = registry.refresh()
    assert receipt["consistent"] is True
    assert receipt["missing"] == []
    assert receipt["verified"] == 2

    # A view whose leaf is gone must still be reported, not silently passed.
    parquet.unlink()
    receipt = registry.refresh()
    assert receipt["consistent"] is False
    assert identity in receipt["missing"]


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
