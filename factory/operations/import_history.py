"""Free source pilot: download -> bounded exact import -> structural readback.

No historical strategy validation or Gold monetary specification is inferred.
"""

import argparse
import json
from pathlib import Path
import time
import resource
import os

from factory.data.histdata import download, quotes_from_archive, PARSER_VERSION
from factory.data.streaming import StreamingCatalog
from factory.data import atomic_bytes, sha256
from factory.provenance import source_identity


def main():
    parent = os.environ.get("FACTORY_SUPERVISED_PARENT_PID")
    if parent:
        from apps.coordinator.supervision import bind_parent

        bind_parent(int(parent))
    parser = argparse.ArgumentParser()
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--year", type=int, choices=[2025, 2026], required=True)
    parser.add_argument("--month", type=int, choices=range(1, 13), required=True)
    parser.add_argument("--archives", default=".local/histdata-archives")
    parser.add_argument("--catalog", default=".local/historical-catalog")
    parser.add_argument("--batch-rows", type=int, default=8192)
    parser.add_argument("--refresh-source", action="store_true")
    parser.add_argument("--registry-state", type=Path)
    args = parser.parse_args()
    context = source_identity()
    started, cpu = time.perf_counter(), time.process_time()
    source = (
        download(args.archives, args.instrument, args.year, args.month, refresh=True)
        if args.refresh_source
        else download(args.archives, args.instrument, args.year, args.month)
    )
    provenance = {
        "source": source["page_url"],
        "license": source["usage"],
        "provider": "HistData.com",
        "synthetic": False,
        "source_timezone": source["source_timezone"],
        "parser_version": PARSER_VERSION,
        "provider_faq": "https://www.histdata.com/f-a-q/",
        "raw_zip_contains_provider_notices": True,
        "volume_status": "not supplied; fourth-column placeholder ignored per provider FAQ",
        "limitations": [
            "calendar gaps unclassified",
            "provider-specific quotes, not brokerage fills",
            "Gold pip/contract/margin metadata remains UNKNOWN_SPEC",
        ],
    }
    manifest = StreamingCatalog(args.catalog).commit(
        quotes_from_archive(source), source["archive"], provenance, args.batch_rows
    )
    from calendar import timegm
    from factory.data import Catalog
    from factory.data.versions import SourceSlot, SourceVersions

    next_year, next_month = (args.year + 1, 1) if args.month == 12 else (args.year, args.month + 1)
    slot = SourceSlot(
        source_id=manifest["source_id"],
        instrument=args.instrument,
        synthetic=False,
        start_ns=(timegm((args.year, args.month, 1, 0, 0, 0)) + 5 * 3600) * 10**9,
        end_ns=(timegm((next_year, next_month, 1, 0, 0, 0)) + 5 * 3600) * 10**9,
    )
    observation_id = SourceVersions(
        args.registry_state or Path(args.catalog).resolve().parent, Catalog(args.catalog)
    ).observe(slot, manifest["dataset_hash"])
    report = {
        "status": "STRUCTURAL_IMPORT_PASS",
        "historical_validation": False,
        "source": source,
        "dataset": manifest,
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - cpu,
        "batch_rows": args.batch_rows,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "source_context": context,
        "source_observation_id": observation_id,
        "source_slot": slot.model_dump(),
        "selection_status": "OBSERVED_NOT_AUTOMATICALLY_SELECTED_OR_APPROVED",
        "source_context_unchanged": source_identity() == context,
    }
    path = Path(args.catalog) / f"{args.instrument}-{args.year}{args.month:02}-import-report.json"
    receipts = Path(args.catalog) / "import-receipts"
    if path.exists():
        prior = path.read_bytes()
        atomic_bytes(receipts / (sha256(path) + ".json"), prior)
    encoded = (json.dumps(report, indent=2) + "\n").encode()
    import hashlib

    atomic_bytes(receipts / (hashlib.sha256(encoded).hexdigest() + ".json"), encoded)
    atomic_bytes(path, encoded)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
