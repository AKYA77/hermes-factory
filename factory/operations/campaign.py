"""Reproducible synthetic engine campaign. This is not historical validation.

Each strategy gets its own Nautilus engine. Small isolated batches amortize imports
for this test harness; the production coordinator still isolates every job.
"""

import argparse
from collections import Counter
from dataclasses import replace, asdict
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

import psutil

from apps.coordinator.worker import run
from factory.contracts import ExperimentContract, Signal, StrategySpec, fingerprint, serialize
from factory.data import Catalog, atomic_bytes
from factory.experiments import Store
from factory.instruments import synthetic_profile
from factory.operations.fixtures import seed

SYMBOLS = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD")
FAMILIES = ("momentum", "mean_reversion", "breakout")


def setup(root, count):
    if not 1 <= count <= 1200:
        raise ValueError("count must be 1..1200 for this finite unique grid")
    root = Path(root)
    store = Store(root / "factory.sqlite")
    base = seed(root, 480)
    original = list(Catalog(root / "catalog").read(base["contract"]["dataset_hash"]))
    datasets = {}
    for symbol in SYMBOLS:
        quotes = [replace(q, instrument_id=symbol) for q in original]
        m = Catalog(root / "catalog").commit(
            quotes,
            serialize([asdict(q) for q in quotes]).encode(),
            {
                "source": "synthetic sine campaign/v1",
                "license": "project test data",
                "synthetic": True,
            },
        )
        datasets[symbol] = m["dataset_hash"]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    identities = []
    for i in range(count):
        symbol = SYMBOLS[i % 4]
        spec = StrategySpec(
            instrument=symbol,
            timeframe=("M1", "M5")[(i // 12) % 2],
            signal=Signal(
                operator=FAMILIES[(i // 4) % 3], lookback=2 + (i // 120) % 10, threshold="1"
            ),
            stop_ticks=(20, 40, 60, 80, 100)[(i // 24) % 5],
        )
        profile = synthetic_profile(symbol)
        raw = dict(
            base["contract"],
            strategy_hash=spec.strategy_hash,
            dataset_hash=datasets[symbol],
            instrument_hash=fingerprint(profile),
            code_revision=revision,
            evaluation_policy="synthetic-campaign/v1",
        )
        contract = ExperimentContract.model_validate(raw)
        payload = {
            "strategy": spec.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
            "contract": contract.model_dump(mode="json"),
        }
        store.register_strategy(spec)
        store.enqueue("research", payload, contract.experiment_hash, actor="synthetic-campaign")
        identities.append(
            {"strategy_hash": spec.strategy_hash, "experiment_hash": contract.experiment_hash}
        )
    if len({x["strategy_hash"] for x in identities}) != count:
        raise ValueError("grid contains duplicates")
    plan = {
        "schema": "synthetic-campaign/v1",
        "count": count,
        "rows_per_replay": 480,
        "synthetic": True,
        "source_commit": revision,
        "datasets": datasets,
        "identities": identities,
        "scope": "4 USD-quoted Forex pairs, 3 families, M1/M5; no historical or OOS claims",
    }
    path = root / "plan.json"
    if path.exists() and json.loads(path.read_text()) != plan:
        raise ValueError("campaign plan differs; use a new directory")
    atomic_bytes(path, serialize(plan).encode())
    return store


def batch(root, size):
    store = Store(Path(root) / "factory.sqlite")
    for _ in range(size):
        job = store.claim(lease_seconds=300)
        if not job:
            break
        try:
            payload = json.loads(job["payload"])
            result = run(payload, root)
            store.complete_experiment(
                ExperimentContract.model_validate(payload["contract"]),
                StrategySpec.model_validate(payload["strategy"]),
                result["result"],
                result["artifact_hash"],
                job["job_id"],
                job["lease_token"],
            )
        except Exception as exc:
            store.finish(
                job["job_id"], job["lease_token"], error=type(exc).__name__ + ": " + str(exc)
            )
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def verify(root):
    root = Path(root)
    plan = json.loads((root / "plan.json").read_text())
    store = Store(root / "factory.sqlite")
    experiments = store.rows("SELECT * FROM experiments")
    failures = []
    empty = []
    totals = Counter()
    coverage = Counter()
    for row in experiments:
        result = json.loads(row["result_json"])
        spec = json.loads(
            store.rows(
                "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (row["strategy_id"],)
            )[0]["spec_json"]
        )
        coverage[(row["instrument"], spec["signal"]["operator"], spec["timeframe"])] += 1
        if fingerprint(result) != row["artifact_hash"]:
            failures.append([row["run_id"], "result hash mismatch"])
        artifact = root / "artifacts" / f"{row['run_id']}.json"
        if fingerprint(json.loads(artifact.read_text())) != row["artifact_hash"]:
            failures.append([row["run_id"], "artifact hash mismatch"])
        if result["rejections"]:
            failures.append([row["run_id"], "engine rejection", result["rejections"]])
        if len(result["diagnostics"]) != len(result["trades"]):
            failures.append([row["run_id"], "diagnostic count mismatch"])
        if not result["trades"]:
            empty.append(row["run_id"])
        for trade in result["trades"]:
            from decimal import Decimal as D

            entry = D(trade["entry_fill"]["price"])
            if abs(D(trade["target"]) - entry) != 3 * abs(entry - D(trade["stop"])):
                failures.append([row["run_id"], "3R invariant"])
            if D(trade["risk"]) > D(trade["equity_before"]) * D(".1"):
                failures.append([row["run_id"], "risk budget exceeded"])
            totals["completed_trades"] += 1
        totals["signals_screened"] += result["signals_screened"]
        totals["quote_events_replayed"] += result["quote_count"]
        totals["open_at_sample_end"] += bool(result["open_trade"])
        totals["skipped_opportunities"] += len(result["skips"])
    states = store.rows("SELECT state,count(*) AS count FROM jobs GROUP BY state")
    if len(experiments) != plan["count"]:
        failures.append(["campaign", "completed experiment count mismatch"])
    if store.rows("SELECT count(*) AS n FROM jobs WHERE state!='COMPLETED'")[0]["n"]:
        failures.append(["campaign", "noncompleted jobs"])
    return {
        "unique_specs": plan["count"],
        "completed_replays": len(experiments),
        "job_states": states,
        "assertion_failures": failures,
        "zero_trade_runs": empty,
        "totals": dict(totals),
        "coverage": [
            {"instrument": k[0], "family": k[1], "timeframe": k[2], "runs": v}
            for k, v in sorted(coverage.items())
        ],
    }


def campaign(root, count, batch_size):
    root = Path(root).resolve()
    started = time.perf_counter()
    store = setup(root, count)
    measurements = []
    env = os.environ.copy()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS"):
        env[name] = "1"
    while store.rows("SELECT count(*) AS n FROM jobs WHERE state='QUEUED'")[0]["n"]:
        before = time.perf_counter()
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "factory.operations.campaign",
                "--state",
                str(root),
                "--batch",
                str(batch_size),
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        peak = 0
        proc = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                peak = max(peak, proc.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            time.sleep(0.05)
        stdout, stderr = child.communicate()
        if child.returncode:
            raise RuntimeError(stderr[-4000:])
        reported = json.loads(stdout)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        measurements.append(
            {
                "wall_seconds": time.perf_counter() - before,
                "cpu_seconds": after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
                "peak_rss_bytes": max(peak, reported["peak_rss_bytes"]),
            }
        )
        completed = store.rows("SELECT count(*) AS n FROM jobs WHERE state='COMPLETED'")[0]["n"]
        atomic_bytes(
            root / "progress.json",
            serialize(
                {
                    "completed": completed,
                    "requested": count,
                    "batches": len(measurements),
                    "elapsed_seconds": time.perf_counter() - started,
                }
            ).encode(),
        )
        print(f"{completed}/{count} completed", flush=True)
    checks = verify(root)
    report = {
        "status": "SOFTWARE_CHECKS_PASSED" if not checks["assertion_failures"] else "FAILED",
        "operation_ready": False,
        "synthetic": True,
        "checks": checks,
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": sum(m["cpu_seconds"] for m in measurements),
        "peak_worker_rss_bytes": max((m["peak_rss_bytes"] for m in measurements), default=0),
        "batch_size": batch_size,
        "batches": measurements,
        "plan": json.loads((root / "plan.json").read_text()),
        "hardware": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "ram": psutil.virtual_memory().total,
            "cpu_count": os.cpu_count(),
        },
        "versions": {
            k: importlib.metadata.version(k) for k in ("nautilus_trader", "pyarrow", "numpy")
        },
        "limitations": [
            "synthetic 8-hour sample, not 2025/2026 market data",
            "no strategy profitability claim",
            "batch test harness amortizes imports; production isolates every job",
            "not Contabo/8GB stress or complete blueprint acceptance",
            "open positions at sample end are censored, not fabricated closes",
        ],
    }
    atomic_bytes(root / "report.json", json.dumps(report, indent=2).encode())
    print(
        json.dumps({k: v for k, v in report.items() if k not in ("batches", "plan", "checks")}),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--batch", type=int)
    args = parser.parse_args()
    if args.batch:
        print(json.dumps({"peak_rss_bytes": batch(args.state, args.batch)}))
    else:
        result = campaign(args.state, args.count, args.batch_size)
        raise SystemExit(0 if result["status"] == "SOFTWARE_CHECKS_PASSED" else 1)
