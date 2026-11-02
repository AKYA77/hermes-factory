"""Free source pilot: download -> bounded exact import -> structural readback.

No historical strategy validation or Gold monetary specification is inferred.
"""

import argparse
import json
from pathlib import Path
import time

from factory.data.histdata import download, quotes_from_archive, PARSER_VERSION
from factory.data.streaming import StreamingCatalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--year", type=int, choices=[2025, 2026], required=True)
    parser.add_argument("--month", type=int, choices=range(1, 13), required=True)
    parser.add_argument("--archives", default=".local/histdata-archives")
    parser.add_argument("--catalog", default=".local/historical-catalog")
    parser.add_argument("--batch-rows", type=int, default=8192)
    args = parser.parse_args()
    started, cpu = time.perf_counter(), time.process_time()
    source = download(args.archives, args.instrument, args.year, args.month)
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
    report = {
        "status": "STRUCTURAL_IMPORT_PASS",
        "historical_validation": False,
        "source": source,
        "dataset": manifest,
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - cpu,
        "batch_rows": args.batch_rows,
    }
    path = Path(args.catalog) / f"{args.instrument}-{args.year}{args.month:02}-import-report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
