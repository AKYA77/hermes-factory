from dataclasses import replace
from decimal import Decimal as D
from datetime import datetime, timezone
import zipfile
import pytest
from factory.data import Catalog
from factory.data.histdata import parse_line, inspect_archive
from factory.data.streaming import StreamingCatalog


def test_fixed_est_is_not_dst_and_prices_reversible():
    q = parse_line("20250701 120000123,1.123456,1.123457,0", "EURUSD", 0, "b")
    expected = int(datetime(2025, 7, 1, 17, tzinfo=timezone.utc).timestamp()) * 10**9 + 123000000
    assert q.event_ts_utc_ns == expected and q.source_precision == "millisecond"
    assert D(q.bid_int) / q.price_scale == D("1.123456")
    gold = parse_line("20250102 010000001,2650.123000,2650.234000,0", "XAUUSD", 0, "b")
    assert D(gold.bid_int) / gold.price_scale == D("2650.123")


@pytest.mark.parametrize(
    "line",
    [
        "20250101 000000000,1.0000001,1.0000002,0",
        "20250101 000000000,NaN,1,0",
        "20250101 00000000,1,2,0",
    ],
)
def test_precision_or_time_ambiguity_rejected(line):
    with pytest.raises(ValueError):
        parse_line(line, "EURUSD", 0, "b")


def test_bounded_stream_roundtrip_and_duplicates(tmp_path):
    source = tmp_path / "source.csv"
    line = "20250102 010000001,1.123450,1.123460,0"
    source.write_text((line + "\n") * 15)

    def stream():
        for i in range(15):
            yield parse_line(line, "EURUSD", i, "raw")

    cat = StreamingCatalog(tmp_path / "catalog")
    m = cat.commit(
        stream(),
        source,
        {"source": "synthetic source fixture", "license": "test only", "synthetic": True},
        batch_rows=4,
    )
    assert m["rows"] == 15 and m["parquet_row_groups"] == 4 and m["readback_exact"]
    assert m["consecutive_exact_duplicates_retained"] == 14
    assert list(Catalog(tmp_path / "catalog").read(m["dataset_hash"])) == list(stream())
    assert cat.commit(stream(), source, m["provenance"], batch_rows=4) == m


def test_invalid_partition_never_commits(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("synthetic")
    q = parse_line("20250102 010000001,1.2,1.3,0", "EURUSD", 0, "raw")
    cat = StreamingCatalog(tmp_path / "catalog")
    with pytest.raises(ValueError, match="QUARANTINED"):
        cat.commit(
            iter([q, replace(q, bid_int=1400000, original_record_order=1)]),
            source,
            {"source": "synthetic", "license": "test", "synthetic": True},
            batch_rows=1,
        )
    assert not list((tmp_path / "catalog").glob("*/manifest.json"))
    assert list((tmp_path / "catalog").glob(".pending-*/failure.json"))


def test_archive_instrument_and_paths_are_checked(tmp_path):
    path = tmp_path / "data.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("../DAT_ASCII_EURUSD_T_202501.csv", "bad")
    with pytest.raises(ValueError):
        inspect_archive(path, "EURUSD", 2025, 1)
