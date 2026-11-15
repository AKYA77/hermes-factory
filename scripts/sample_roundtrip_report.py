#!/usr/bin/env python3
"""Emit the C2 Forex and Gold sample round-trip / checksum / coverage report.

The integration test tests/integration/test_sample_roundtrip_report.py enforces
the same checks on every CI run; this script produces the human-readable,
committed artifact for the acceptance record. Both samples are synthetic
fixtures -- structural pipeline verification, not market validation.

    env -u PYTHONPATH .venv/bin/python scripts/sample_roundtrip_report.py \
        --output reports/sample-roundtrip-report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "integration"))

from test_sample_roundtrip_report import FOREX, GOLD, _roundtrip  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for label, spec in (("forex", FOREX), ("gold", GOLD)):
            case_root = root / label
            case_root.mkdir(parents=True, exist_ok=True)
            manifest = _roundtrip(case_root, spec)
            rows[label] = {
                "instrument": manifest["instrument"],
                "rows": manifest["rows"],
                "dataset_hash": manifest["dataset_hash"],
                "source_sha256": manifest["source_sha256"],
                "parquet_sha256": manifest["parquet_sha256"],
                "quote_stream_sha256": manifest["quote_stream_sha256"],
                "first_ns": manifest["first_ns"],
                "latest_verified_ns": manifest["latest_verified_ns"],
                "gap_count_over_60s": manifest["gap_count_over_60s"],
                "parquet_row_groups": manifest["parquet_row_groups"],
                "price_scale": manifest["price_scale"],
                "observed_price_quantum": manifest["observed_price_quantum"],
                "readback_exact": manifest["readback_exact"],
                "quality_status": manifest["quality_status"],
                "checks": [
                    "raw source hash matches the published manifest",
                    "canonical parquet hash matches the published manifest",
                    "partition reads back byte-exactly to the input stream",
                    "row count, first and last timestamps and contiguity verified",
                    "re-importing identical bytes reproduces the same dataset identity",
                ],
            }

    report = {
        "schema_version": "sample-roundtrip-report/v1",
        "forex_and_gold_samples": rows,
        "synthetic_only": True,
        "note": "Generated fixtures exercising the streaming importer, canonical "
        "parquet, manifest hashing and read-back identity. Structural data "
        "pipeline verification only -- not market validation, not DATA_READY.",
    }
    text = json.dumps(report, indent=1)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
