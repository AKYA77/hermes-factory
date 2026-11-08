"""Data source registry and storage inventory over the catalog.

Read-only reporting over committed partitions. A refresh re-verifies each
partition's parquet digest against its manifest and returns a receipt; it never
mutates catalog data.
"""

import json
from collections import defaultdict
from pathlib import Path

from factory.data import sha256


class SourceRegistry:
    def __init__(self, catalog_root):
        self.root = Path(catalog_root)

    def _manifests(self):
        for path in sorted(self.root.glob("*/manifest.json")):
            try:
                yield path, json.loads(path.read_text())
            except (OSError, ValueError):
                continue

    def list(self):
        sources = []
        for path, manifest in self._manifests():
            parquet = path.parent / "quotes.parquet"
            sources.append(
                {
                    "dataset_hash": manifest.get("dataset_hash"),
                    "instrument": manifest.get("instrument"),
                    "rows": manifest.get("rows"),
                    "first_ns": manifest.get("first_ns"),
                    "latest_verified_ns": manifest.get("latest_verified_ns"),
                    "fidelity": manifest.get("fidelity"),
                    "provenance": manifest.get("provenance"),
                    "bytes": parquet.stat().st_size if parquet.exists() else 0,
                }
            )
        return sources

    def detail(self, identity):
        for source in self.list():
            if source["dataset_hash"] == identity:
                return source
        raise KeyError(identity)

    def storage(self):
        sources = self.list()
        by_instrument = defaultdict(lambda: {"partitions": 0, "rows": 0, "bytes": 0})
        for source in sources:
            entry = by_instrument[source["instrument"]]
            entry["partitions"] += 1
            entry["rows"] += source["rows"]
            entry["bytes"] += source["bytes"]
        return {
            "partitions": len(sources),
            "rows": sum(source["rows"] for source in sources),
            "bytes": sum(source["bytes"] for source in sources),
            "by_instrument": dict(by_instrument),
        }

    def refresh(self):
        """Re-verify every partition parquet digest against its manifest."""
        verified, mismatched, missing = [], [], []
        for path, manifest in self._manifests():
            identity = manifest.get("dataset_hash")
            parquet = path.parent / "quotes.parquet"
            if not parquet.exists():
                missing.append(identity)
                continue
            digest = sha256(parquet)
            if digest == manifest.get("parquet_sha256"):
                verified.append(identity)
            else:
                mismatched.append(
                    {
                        "dataset_hash": identity,
                        "manifest": manifest.get("parquet_sha256"),
                        "actual": digest,
                    }
                )
        return {
            "status": "REFRESH_COMPLETE",
            "verified": len(verified),
            "mismatched": mismatched,
            "missing": missing,
            "consistent": not mismatched and not missing,
        }
