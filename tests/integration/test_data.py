import pytest
from factory.data import Catalog
from factory.features import closed_bars
from conftest import quotes


def test_T04_roundtrip(tmp_path):
    q = quotes([(110001, 110003), (110002, 110006)])
    cat = Catalog(tmp_path)
    m = cat.commit(
        q,
        b"synthetic source",
        {"source": "fixture", "license": "project synthetic", "synthetic": True},
    )
    assert list(cat.read(m["dataset_hash"])) == q
    assert m["rows"] == 2
    assert cat.commit(q, b"synthetic source", m["provenance"]) == m


def test_T05_quarantine_corruption(tmp_path):
    cat = Catalog(tmp_path)
    with pytest.raises(ValueError, match="QUARANTINED"):
        cat.commit(quotes([(2, 1)]), b"bad", {"source": "fixture", "license": "synthetic"})
    assert list(tmp_path.glob("quarantine/*.json"))
    assert not list(tmp_path.glob("*/manifest.json"))
    m = cat.commit(quotes([(1, 2)]), b"ok", {"source": "fixture", "license": "synthetic"})
    (tmp_path / m["dataset_hash"] / "quotes.parquet").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="CORRUPT"):
        list(cat.read(m["dataset_hash"]))


def test_T06_closed_availability():
    q = quotes([(110000, 110010)] * 4, step=1800 * 10**9)
    bars = list(closed_bars(q, "H1"))
    assert len(bars) == 1
    assert bars[0].available_at == q[2].event_ts_utc_ns
    assert not [b for b in bars if b.available_at <= q[1].event_ts_utc_ns]


def test_legacy_manifest_provenance_is_bound(tmp_path):
    import json

    cat = Catalog(tmp_path)
    m = cat.commit(
        quotes([(110000, 110010)]),
        b"fixture",
        {"source": "synthetic", "license": "test", "synthetic": True},
    )
    path = tmp_path / m["dataset_hash"] / "manifest.json"
    m["provenance"]["synthetic"] = False
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="identity"):
        cat.verify(m["dataset_hash"])
