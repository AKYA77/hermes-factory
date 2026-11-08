"""Bounded soak run under explicit resource limits.

A soak run repeats a bounded synthetic work cycle and samples resident memory and
swap usage. It reports whether the configured limits were respected and archives
the metrics. It is a synthetic development soak, never a VPS or historical
throughput claim.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil

from factory.data import atomic_bytes
from factory.operations.fixtures import seed

DEFAULT_MAX_RSS_BYTES = 8 * 1024**3
DEFAULT_MAX_WALL_SECONDS = 3600


def _sample(process):
    try:
        return process.memory_info().rss
    except psutil.NoSuchProcess:
        return 0


def run(
    output,
    iterations=3,
    max_rss_bytes=DEFAULT_MAX_RSS_BYTES,
    max_wall_seconds=DEFAULT_MAX_WALL_SECONDS,
):
    if iterations < 1:
        raise ValueError("soak requires at least one iteration")
    if max_rss_bytes < 1 or max_wall_seconds < 1:
        raise ValueError("soak limits must be positive")
    records = []
    peak_rss = 0
    peak_swap = 0
    start = time.perf_counter()
    for index in range(iterations):
        if time.perf_counter() - start > max_wall_seconds:
            records.append({"iteration": index, "status": "STOPPED_WALL_LIMIT"})
            break
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = seed(root, 1200)
            inp = root / "input.json"
            inp.write_text(json.dumps(payload, sort_keys=True))
            out = root / "out.json"
            env = os.environ.copy()
            for key in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "RAYON_NUM_THREADS",
            ):
                env[key] = "1"
            before = time.perf_counter()
            child = subprocess.Popen(
                [sys.executable, "-m", "apps.coordinator.worker", str(inp), str(root), str(out)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process = psutil.Process(child.pid)
            stopped = False
            while child.poll() is None:
                peak_rss = max(peak_rss, _sample(process))
                peak_swap = max(peak_swap, psutil.swap_memory().used)
                if peak_rss > max_rss_bytes:
                    child.kill()
                    stopped = True
                    records.append({"iteration": index, "status": "STOPPED_RSS_LIMIT"})
                    break
                time.sleep(0.02)
            elapsed = time.perf_counter() - before
            if child.returncode and not stopped:
                raise RuntimeError(out.read_text() if out.exists() else "soak worker failed")
            if stopped:
                continue
            records.append(
                {
                    "iteration": index,
                    "status": "COMPLETE",
                    "wall_seconds": elapsed,
                    "completed_trades": len(json.loads(out.read_text())["result"]["trades"]),
                }
            )
    wall = time.perf_counter() - start
    within = peak_rss <= max_rss_bytes and wall <= max_wall_seconds
    report = {
        "status": "BOUNDED_SYNTHETIC_SOAK",
        "scope": "NOT VPS / NOT HISTORICAL / NOT MARKET VALIDATION",
        "iterations_requested": iterations,
        "iterations_completed": sum(1 for r in records if r["status"] == "COMPLETE"),
        "peak_rss_bytes_sampled": peak_rss,
        "peak_swap_bytes": peak_swap,
        "wall_seconds": wall,
        "limits": {"max_rss_bytes": max_rss_bytes, "max_wall_seconds": max_wall_seconds},
        "within_limits": within,
        "oom_detected": peak_rss > max_rss_bytes,
        "uncontrolled_swap": peak_swap > 0,
        "records": records,
        "limitations": [
            "Synthetic fixture only; no Forex/Gold corpus",
            "Sampled RSS at 20ms may miss shorter peaks",
            "Swap presence is reported, not treated as failure",
            "No 8GB stress claim beyond the configured limit",
        ],
    }
    atomic_bytes(output, json.dumps(report, indent=2, sort_keys=True).encode())
    return report


if __name__ == "__main__":
    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    print(
        json.dumps(
            run(sys.argv[1] if len(sys.argv) > 1 else "reports/soak/soak-report.json", iterations),
            indent=2,
        )
    )
