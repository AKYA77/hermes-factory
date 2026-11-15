"""Single heavy subprocess, fenced leases, measured resources and recurring research."""

import fcntl
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

import psutil
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec
from factory.experiments import Store
from factory.operations.resources import memory_headroom


def cycle(store, root, timeout=300, memory_limit_bytes=3758096384):
    root = Path(root)
    # Advisory lock is process scoped and released by the kernel on SIGKILL.
    with (root / "coordinator.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return _cycle(store, root, timeout, memory_limit_bytes)


def _cycle(store, root, timeout, memory_limit_bytes):
    if store.paused():
        return False
    if (
        memory_headroom()["available_bytes"] < memory_limit_bytes + 1024**3
        or psutil.disk_usage(root).free < 256 * 1024**2
    ):
        return False
    from apps.coordinator.research import maintenance

    try:
        maintenance(store, root)
    except ValueError as exc:
        store.audit("research", "maintenance_blocked", {"error": str(exc)[:1000]})
    job = store.claim(lease_seconds=timeout + 30, respect_pause=True)
    if not job:
        return False
    if job["kind"] not in ("research", "validation"):
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
    env["FACTORY_SUPERVISED_PARENT_PID"] = str(os.getpid())
    started = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    resources = {}
    child = None
    try:
        spec = StrategySpec.model_validate(payload["strategy"])
        store.register_strategy(spec)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            inp, out = Path(temp) / "input.json", Path(temp) / "output.json"
            inp.write_text(job["payload"])
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "apps.coordinator.worker"
                    if job["kind"] == "research"
                    else "apps.coordinator.evaluation_worker",
                    str(inp),
                    str(root),
                    str(out),
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            process = psutil.Process(child.pid)
            peak = 0
            next_heartbeat = time.monotonic() + 10
            next_control_check = time.monotonic() + 0.5
            while child.poll() is None:
                now = time.monotonic()
                if now - started > timeout:
                    raise subprocess.TimeoutExpired("research worker", timeout)
                try:
                    peak = max(peak, process.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                if peak > memory_limit_bytes:
                    raise ValueError("WORKER_MEMORY_LIMIT")
                if now >= next_control_check:
                    state = store.rows(
                        "SELECT state,lease_token FROM jobs WHERE job_id=?", (job["job_id"],)
                    )[0]
                    if state["state"] != "RUNNING" or state["lease_token"] != job["lease_token"]:
                        raise ValueError("STALE_LEASE")
                    next_control_check = now + 0.5
                if now >= next_heartbeat:
                    store.heartbeat(job["job_id"], job["lease_token"], seconds=30)
                    next_heartbeat = now + 10
                time.sleep(0.05)
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            result = (
                json.loads(out.read_text())
                if out.exists()
                else {"error": "WORKER_EXIT_" + str(child.returncode)}
            )
            resources = {
                "wall_seconds": time.monotonic() - started,
                "cpu_seconds": after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
                "peak_rss_bytes": (result.get("resources") or {}).get("peak_rss_bytes"),
                "peak_rss_bytes_sampled": peak,
                "memory_sample_seconds": 0.05,
            }
            if child.returncode or "error" in result:
                store.finish(
                    job["job_id"],
                    job["lease_token"],
                    result={"resources": resources},
                    error=result.get("error", "worker failed"),
                )
            elif job["kind"] == "validation":
                if result.get("result_kind") != "EVALUATION":
                    raise ValueError("validation worker result kind mismatch")
                store.complete_evaluation(
                    ExperimentContract.model_validate(payload["contract"]),
                    result["result"],
                    result["artifact_hash"],
                    job["job_id"],
                    job["lease_token"],
                    resources,
                )
            elif result.get("result_kind") == "SCREENED_OUT":
                from factory.screening import verify_pruned

                receipt = verify_pruned(root, payload["contract"], result)
                store.finish(
                    job["job_id"],
                    job["lease_token"],
                    result={
                        "screen": receipt.model_dump(mode="json"),
                        "screen_artifact_hash": result["screen_artifact_hash"],
                        "resources": resources,
                    },
                )
                store.audit(
                    "research",
                    "tier0_rejected",
                    {
                        "experiment_hash": receipt.experiment_hash,
                        "screen_artifact_hash": result["screen_artifact_hash"],
                    },
                )
            else:
                completed = ExperimentContract.model_validate(payload["contract"])
                store.complete_experiment(
                    completed,
                    StrategySpec.model_validate(payload["strategy"]),
                    result["result"],
                    result["artifact_hash"],
                    job_id=job["job_id"],
                    token=job["lease_token"],
                    resources=resources,
                )
                historical_completion_diagnostics(root, store, payload, completed)
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as exc:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
        if str(exc) == "STALE_LEASE":
            store.audit("coordinator", "stale_completion_rejected", {"job_id": job["job_id"]})
        else:
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            resources.update(
                {
                    "wall_seconds": time.monotonic() - started,
                    "cpu_seconds": after.ru_utime
                    + after.ru_stime
                    - usage.ru_utime
                    - usage.ru_stime,
                }
            )
            try:
                store.finish(
                    job["job_id"],
                    job["lease_token"],
                    result={"resources": resources},
                    error=type(exc).__name__ + ": " + str(exc),
                    retryable=isinstance(exc, OSError),
                )
            except ValueError as stale:
                if str(stale) != "STALE_LEASE":
                    raise
                store.audit("coordinator", "stale_failure_rejected", {"job_id": job["job_id"]})
    return True


HISTORICAL_DIAGNOSTIC_ATTESTATION = (
    "Authorize training-only feature diagnostics and mandatory native evidence; "
    "no approximate pruning"
)


def historical_completion_diagnostics(root, store, payload, contract):
    """Fenced completion produces the historical diagnostic for cohort members.

    The native artifact is never mutated. The diagnostic is a separate
    content-addressed artifact with its own hash and immutable audit lineage. It
    rechecks reviewed admission, quarantine, protected holdout, source and code
    scope before feature access and again at publication. A blocked diagnostic is
    recorded as an immutable audit event; it never reinterprets the consumed
    native evaluation.
    """
    from factory.screening.historical import HistoricalShadowRequest, diagnose
    from factory.screening.historical_cohorts import selected_historical_cohort

    if selected_historical_cohort(store, contract) is None:
        return
    profile = InstrumentSpec.model_validate(payload["profile"])
    if profile.synthetic:
        return
    try:
        diagnose(
            root,
            HistoricalShadowRequest(
                experiment_hash=contract.experiment_hash,
                profile=profile,
                authorized_by="coordinator-fenced-historical-completion",
                attestation=HISTORICAL_DIAGNOSTIC_ATTESTATION,
            ),
        )
    except ValueError as exc:
        store.audit(
            "coordinator",
            "historical_completion_diagnostic_blocked",
            {"experiment_hash": contract.experiment_hash, "error": str(exc)[:1000]},
        )


def serve(root):
    root = Path(root)
    store = Store(root / "factory.sqlite")
    while True:
        if not cycle(store, root):
            time.sleep(2)
