"""Measured synthetic developer workload. Never a historical/VPS throughput claim."""

import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time

import psutil
import pyarrow.parquet as pq
from factory.contracts import ExperimentContract, StrategySpec, fingerprint, serialize
from factory.data import Catalog, atomic_bytes
from factory.operations.fixtures import seed
from factory.strategies import compile_signals


def cgroup_limit(name):
    """Read the cgroup v2 limit that actually applies to this process.

    The root cgroup usually has no controllers delegated, so
    `/sys/fs/cgroup/<name>` does not exist even on a cgroup v2 host, and a
    process is often nested several levels below the root. Walk from the
    process's own cgroup (taken from `/proc/self/cgroup`) up to the root and
    return the nearest delegated limit. Controllers that are not delegated
    anywhere are reported as ``"not-delegated"`` rather than crashing.
    """
    relative = ""
    try:
        for line in Path("/proc/self/cgroup").read_text().splitlines():
            # Format is "<hierarchy-id>:<controllers>:<path>"; the path may be
            # empty (root) or start with '/'.
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[2]:
                relative = parts[2].lstrip("/")
                break
    except OSError:
        pass
    while True:
        candidate = Path("/sys/fs/cgroup") / relative / name
        if candidate.exists():
            return candidate.read_text().strip()
        if not relative:
            break
        relative = relative.rsplit("/", 1)[0] if "/" in relative else ""
    return "not-delegated"


def run(output):
    records = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        before = time.perf_counter()
        payload = seed(root, 2000)
        records.append(
            {
                "stage": "synthetic-generation-plus-parquet-commit",
                "wall_seconds": time.perf_counter() - before,
                "rows": 2000,
            }
        )
        c = ExperimentContract.model_validate(payload["contract"])
        cat = Catalog(root / "catalog")
        for mode in ("first-read-OS-cache-uncontrolled", "warm-read"):
            before = time.perf_counter()
            quotes = list(cat.read(c.dataset_hash))
            records.append(
                {"stage": mode, "wall_seconds": time.perf_counter() - before, "rows": len(quotes)}
            )
        spec = StrategySpec.model_validate(payload["strategy"])
        before = time.perf_counter()
        cpu = time.process_time()
        signals = compile_signals(quotes, spec)
        records.append(
            {
                "stage": "signal-screen",
                "wall_seconds": time.perf_counter() - before,
                "cpu_seconds": time.process_time() - cpu,
                "signals": len(signals),
            }
        )
        table = pq.read_table(root / "catalog" / c.dataset_hash / "quotes.parquet")
        for codec, level in [("zstd", 1), ("zstd", 2), ("zstd", 3), ("snappy", None)]:
            p = root / f"{codec}{level}.parquet"
            before = time.perf_counter()
            cpu = time.process_time()
            kwargs = {"compression_level": level} if level else {}
            pq.write_table(table, p, compression=codec, **kwargs)
            elapsed = time.perf_counter() - before
            assert pq.read_table(p).equals(table)
            records.append(
                {
                    "stage": "compression",
                    "codec": codec,
                    "level": level,
                    "wall_seconds": elapsed,
                    "cpu_seconds": time.process_time() - cpu,
                    "bytes": p.stat().st_size,
                    "roundtrip_equal": True,
                }
            )
        inp = root / "input.json"
        inp.write_text(serialize(payload))
        outputs = []
        for label in ("fresh-worker-first", "fresh-worker-warm-files"):
            out = root / (label + ".json")
            env = os.environ.copy()
            for key in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "RAYON_NUM_THREADS",
            ):
                env[key] = "1"
            before = time.perf_counter()
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            child = subprocess.Popen(
                [sys.executable, "-m", "apps.coordinator.worker", str(inp), str(root), str(out)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process = psutil.Process(child.pid)
            peak = 0
            while child.poll() is None:
                try:
                    peak = max(peak, process.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                time.sleep(0.01)
            elapsed = time.perf_counter() - before
            if child.returncode:
                raise RuntimeError(out.read_text() if out.exists() else "worker failed")
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            result = json.loads(out.read_text())
            outputs.append(fingerprint(result["result"]))
            records.append(
                {
                    "stage": label,
                    "wall_seconds": elapsed,
                    "cpu_seconds": after.ru_utime
                    + after.ru_stime
                    - usage.ru_utime
                    - usage.ru_stime,
                    "peak_rss_bytes_sampled": peak,
                    "quotes": 2000,
                    "completed_trades": len(result["result"]["trades"]),
                    "quote_events_per_wall_second_including_startup": 2000 / elapsed,
                }
            )
        if outputs[0] != outputs[1]:
            raise ValueError("nonreproducible replay artifacts")
        report = {
            "status": "SYNTHETIC_DEVELOPMENT_BENCHMARK",
            "scope": "NOT VPS / NOT HISTORICAL / NOT SOAK",
            "hardware": {
                "os": platform.platform(),
                "machine": platform.machine(),
                "logical_cpus": os.cpu_count(),
                "host_ram_bytes": psutil.virtual_memory().total,
                "cgroup_memory_max": cgroup_limit("memory.max"),
                "cgroup_cpu_max": cgroup_limit("cpu.max"),
            },
            "versions": {
                n: importlib.metadata.version(n)
                for n in ("nautilus_trader", "numpy", "pyarrow", "duckdb", "optuna")
            },
            "dataset_hash": c.dataset_hash,
            "rows": 2000,
            "source": "project synthetic sine fixture/v1",
            "source_urls": {
                "provider": "https://www.histdata.com/download-free-forex-historical-data/",
                "download_endpoint": "https://www.histdata.com/get.php",
                "used_in_this_run": [],
                "note": (
                    "This development benchmark used the project synthetic sine fixture, so no "
                    "provider dataset URL applies to its measurements; the endpoints above are the "
                    "project's canonical acquisition sources."
                ),
            },
            "code_revision": c.code_revision,
            "worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"])),
            "artifact_hashes": outputs,
            "reproducible_exactly": True,
            "measurements": records,
            "limitations": [
                "OS page cache not flushed",
                "sampled RSS at 10ms may miss shorter peaks",
                "two trials only; no statistical speedup claim",
                "no real Forex/Gold corpus",
                "no 8GB stress or Contabo benchmark",
                "screening implementation comparison pending",
            ],
        }
        atomic_bytes(output, json.dumps(report, indent=2, sort_keys=True).encode())
        return report


if __name__ == "__main__":
    report = run(sys.argv[1] if len(sys.argv) > 1 else "reports/benchmark-report.json")
    print(json.dumps(report, indent=2))
