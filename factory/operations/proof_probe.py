"""Cache on/off canonical-verification benchmark; no simulation throughput claim."""

import argparse
import json
from pathlib import Path
import resource
import time

from factory.data import Catalog, atomic_bytes
from factory.contracts import fingerprint
from factory.operations.fixtures import seed
from factory.provenance import source_identity


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=100)
    args = p.parse_args()
    if args.state.exists() or not 2 <= args.repeats <= 1000:
        p.error("new state directory and repeats 2..1000 required")
    context = source_identity()
    payload = seed(args.state, 480)
    identity = payload["contract"]["dataset_hash"]
    measurements = []
    hashes = []
    # Alternate execution order to expose cache/host timing variability, not hide it.
    for cache_size in (0, 32, 32, 0):
        cat = Catalog(args.state / "catalog", proof_cache_size=cache_size)
        wall = time.perf_counter()
        cpu = time.process_time()
        for _ in range(args.repeats):
            manifest = cat.verify(identity, deep=True)
            hashes.append(fingerprint(manifest))
        measurements.append(
            {
                "proof_cache_entries": cache_size,
                "verification_calls": args.repeats,
                "wall_seconds": time.perf_counter() - wall,
                "cpu_seconds": time.process_time() - cpu,
                "cache_hits": cat.verification_cache_hits,
                "uncached_semantic_checks": cat.verification_scans,
                "byte_hashes_checked_every_call": True,
            }
        )
    if len(set(hashes)) != 1 or source_identity() != context:
        raise ValueError("verification parity/source context failed")
    report = {
        "status": "PASS_VERIFICATION_PARITY",
        "scope": "synthetic 480-row canonical verification only; no strategy/historical/VPS throughput",
        "source_context": context,
        "source_context_unchanged": True,
        "dataset_hash": identity,
        "manifest_hash": hashes[0],
        "manifest_equal_cache_on_off": True,
        "rows_per_verification": 480,
        "measurements": measurements,
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "os_page_cache": "uncontrolled; no cold-cache claim",
    }
    atomic_bytes(args.output, json.dumps(report, indent=2, sort_keys=True).encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
