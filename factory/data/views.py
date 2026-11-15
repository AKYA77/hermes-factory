"""Immutable flat multi-partition views. Leaf quotes/source identities never change."""

from dataclasses import dataclass
import json
from factory.contracts import fingerprint
from factory.data import atomic_bytes

VIEW_SCHEMA = "data/view-v1"


@dataclass(frozen=True, slots=True)
class LocatedQuote:
    quote: object
    partition_hash: str
    sequence: int

    def __getattr__(self, name):
        return getattr(self.quote, name)


def _descriptor(catalog, parts, deep):
    if not 1 <= len(parts) <= 512 or len(set(parts)) != len(parts):
        raise ValueError("view requires 1..512 distinct ordered leaf partitions")
    leaves = []
    rows = 0
    units = None
    previous = None
    synthetic = None
    for identity in parts:
        m = catalog.verify(identity, deep=deep)
        if m["schema_version"] == VIEW_SCHEMA:
            raise ValueError("nested views are not supported")
        first = next(catalog.read(identity), None)
        if first is None:
            raise ValueError("empty view leaf")
        current = (first.instrument_id, first.price_scale, first.source_id, first.source_precision)
        if units is None:
            units = current
        if units != current:
            raise ValueError("view instrument/units/provider mismatch")
        flag = bool(m["provenance"].get("synthetic"))
        if synthetic is None:
            synthetic = flag
        if synthetic != flag:
            raise ValueError("cannot mix synthetic and historical leaves")
        if previous is not None and m["first_ns"] < previous:
            raise ValueError(
                "overlapping/reversed view leaves; revisions require explicit selection"
            )
        leaves.append(
            {
                "dataset_hash": identity,
                "offset": rows,
                "rows": m["rows"],
                "first_ns": m["first_ns"],
                "last_ns": m["latest_verified_ns"],
                "source_sha256": m["source_sha256"],
                "parquet_sha256": m["parquet_sha256"],
            }
        )
        rows += m["rows"]
        previous = m["latest_verified_ns"]
    return {
        "schema_version": VIEW_SCHEMA,
        "parts": leaves,
        "instrument": units[0],
        "price_scale": units[1],
        "source_id": units[2],
        "source_precision": units[3],
        "rows": rows,
        "first_ns": leaves[0]["first_ns"],
        "latest_verified_ns": leaves[-1]["last_ns"],
        "provenance": {
            "synthetic": synthetic,
            "source": "immutable ordered canonical leaves",
            "license": "original source/usage receipts retained in each leaf",
        },
        "fidelity": "SYNTHETIC" if synthetic else "SOURCE_BID_ASK",
        "ordering_policy": "leaf order then original source order; equal-time boundary records retained",
        "quality_status": "LEAF_STRUCTURAL_CHECKS_ONLY_CALENDAR_REVIEW_REQUIRED",
    }


def compose(catalog, parts):
    body = _descriptor(catalog, list(parts), True)
    identity = fingerprint(body)
    manifest = {**body, "dataset_hash": identity}
    path = catalog.root / identity / "manifest.json"
    encoded = json.dumps(manifest, sort_keys=True).encode()
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("immutable view differs")
    if not path.exists():
        atomic_bytes(path, encoded)
    return verify_view(catalog, identity, manifest, False)


def verify_view(catalog, identity, manifest, deep):
    body = {k: v for k, v in manifest.items() if k != "dataset_hash"}
    if manifest.get("dataset_hash") != identity or fingerprint(body) != identity:
        raise ValueError("view identity mismatch")
    expected = _descriptor(catalog, [p["dataset_hash"] for p in manifest["parts"]], deep)
    if body != expected:
        raise ValueError("view leaf descriptor changed")
    return manifest


def read_view(catalog, manifest, *, start_ns=None, end_ns=None, batch_rows=8192):
    for part in manifest["parts"]:
        if start_ns is not None and part["last_ns"] < start_ns:
            continue
        if end_ns is not None and part["first_ns"] >= end_ns:
            continue
        for index, quote in catalog.read_indexed(
            part["dataset_hash"], start_ns=start_ns, end_ns=end_ns, batch_rows=batch_rows
        ):
            yield LocatedQuote(quote, part["dataset_hash"], part["offset"] + index)
