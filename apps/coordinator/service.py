"""Leased work execution. One heavy subprocess, bounded runtime and threads."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil
from factory.contracts import ExperimentContract, StrategySpec
from factory.experiments import Store


def cycle(store, root, timeout=300):
    if store.paused():
        return False
    if psutil.virtual_memory().available < 1024**3 or psutil.disk_usage(root).free < 256 * 1024**2:
        return False
    job = store.claim(lease_seconds=timeout + 30)
    if not job:
        return False
    if job["kind"] != "research":
        store.finish(job["job_id"], job["lease_token"], error="unsupported job kind")
        return True
    payload = json.loads(job["payload"])
    env = os.environ.copy()
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMBA_NUM_THREADS",
        "RAYON_NUM_THREADS",
    ):
        env[name] = "1"
    try:
        with tempfile.TemporaryDirectory(dir=root) as temp:
            inp = Path(temp) / "input.json"
            out = Path(temp) / "output.json"
            inp.write_text(job["payload"])
            child = subprocess.run(
                [sys.executable, "-m", "apps.coordinator.worker", str(inp), str(root), str(out)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            result = (
                json.loads(out.read_text())
                if out.exists()
                else {"error": "WORKER_EXIT_" + str(child.returncode)}
            )
            if child.returncode or "error" in result:
                store.finish(
                    job["job_id"], job["lease_token"], error=result.get("error", "worker failed")
                )
            else:
                contract = ExperimentContract.model_validate(payload["contract"])
                spec = StrategySpec.model_validate(payload["strategy"])
                run_id = store.complete_experiment(
                    contract, spec, result["result"], result["artifact_hash"]
                )
                store.finish(job["job_id"], job["lease_token"], result={"run_id": run_id})
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        store.finish(job["job_id"], job["lease_token"], error=type(exc).__name__, retryable=True)
    return True


def serve(root):
    root = Path(root)
    store = Store(root / "factory.sqlite")
    while True:
        if not cycle(store, root):
            time.sleep(2)
