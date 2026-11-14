"""C2: one Forex and one Gold sample round-trip / checksum / coverage report.

Each sample is written through the streaming importer, read back, and checked for
byte-level identity, hash agreement between the raw source, the canonical parquet
stream and the published manifest, and contiguous coverage across the sampled
window. Both are synthetic fixtures; this is a structural data-pipeline check,
not market validation or DATA_READY.
"""

from __future__ import annotations

import json

import pyarrow.parquet as pq

from factory.data import Catalog, Quote, sha256
from factory.data.streaming import StreamingCatalog

FOREX = {"instrument": "EURUSD", "price_scale": 100000, "bid_base": 110000}
GOLD = {"instrument": "XAUUSD", "price_scale": 100, "bid_base": 230000}


def _sample(spec, rows=48):
    """Deterministic one-hour sample at one-minute spacing."""
    start = 1735689600 * 10**9
    return [
        Quote(
            spec["instrument"],
            start + i * 60 * 10**9,
            spec["bid_base"] + ((i * 37) % 113),
            spec["bid_base"] + ((i * 37) % 113) + 2,
            spec["price_scale"],
            "synthetic",
            "roundtrip-fixture",
            i,
        )
        for i in range(rows)
    ]


def _source_file(tmp_path, spec, quotes):
    path = tmp_path / f"{spec['instrument']}.csv"
    lines = [f"{q.event_ts_utc_ns},{q.bid_int},{q.ask_int}" for q in quotes]
    path.write_text("\n".join(lines) + "\n")
    return path


def _roundtrip(tmp_path, spec):
    quotes = _sample(spec)
    source = _source_file(tmp_path, spec, quotes)
    catalog = StreamingCatalog(tmp_path / "catalog")
    manifest = catalog.commit(
        iter(quotes),
        source,
        {
            "source": f"GENERATED {spec['instrument']} sample, not market data",
            "license": "project test fixture",
            "synthetic": True,
        },
        batch_rows=8,
    )

    # Checksum: the manifest must agree with the bytes actually on disk.
    partition_dir = tmp_path / "catalog" / manifest["dataset_hash"]
    parquet_path = partition_dir / "quotes.parquet"
    assert manifest["source_sha256"] == sha256(source), "raw source hash mismatch"
    assert manifest["parquet_sha256"] == sha256(parquet_path), "parquet hash mismatch"

    # Round-trip: reading the partition reproduces the input stream exactly.
    assert manifest["readback_exact"] is True
    assert list(Catalog(tmp_path / "catalog").read(manifest["dataset_hash"])) == quotes

    # Coverage: every sampled minute present, contiguous, no unexplained gaps.
    assert manifest["rows"] == len(quotes)
    assert manifest["first_ns"] == quotes[0].event_ts_utc_ns
    assert manifest["latest_verified_ns"] == quotes[-1].event_ts_utc_ns
    assert manifest["gap_count_over_60s"] == 0
    assert manifest["quality_status"] == "STRUCTURAL_PASS_CALENDAR_REVIEW_REQUIRED"
    assert manifest["parquet_row_groups"] > 1, "the sample should span several row groups"

    # Idempotency: re-importing the same source publishes the same identity.
    again = catalog.commit(
        iter(_sample(spec)),
        source,
        {
            "source": f"GENERATED {spec['instrument']} sample, not market data",
            "license": "project test fixture",
            "synthetic": True,
        },
        batch_rows=8,
    )
    assert again == manifest, "re-import of identical bytes changed the dataset identity"

    return manifest


def test_forex_and_gold_samples_roundtrip_with_matching_checksums_and_coverage(tmp_path):
    forex = _roundtrip(tmp_path, FOREX)
    gold = _roundtrip(tmp_path, GOLD)
    assert forex["instrument"] == "EURUSD" and gold["instrument"] == "XAUUSD"
    assert forex["rows"] == gold["rows"] == 48
    # Each instrument keeps its own price grid.
    assert forex["price_scale"] == 100000 and gold["price_scale"] == 100
    assert forex["observed_price_quantum"] != gold["observed_price_quantum"]


def test_manifest_json_on_disk_matches_the_returned_identity(tmp_path):
    spec = FOREX
    quotes = _sample(spec)
    source = _source_file(tmp_path, spec, quotes)
    catalog = StreamingCatalog(tmp_path / "catalog")
    manifest = catalog.commit(
        iter(quotes),
        source,
        {"source": "GENERATED sample", "license": "test", "synthetic": True},
        batch_rows=8,
    )
    directory = tmp_path / "catalog" / manifest["dataset_hash"]
    on_disk = json.loads((directory / "manifest.json").read_text())
    assert on_disk["dataset_hash"] == manifest["dataset_hash"]
    assert on_disk["quote_stream_sha256"] == manifest["quote_stream_sha256"]
    assert pq.read_metadata(directory / "quotes.parquet").num_rows == manifest["rows"]
