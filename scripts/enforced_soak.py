"""Run the bounded synthetic soak under enforced 4-vCPU / 8-GB limits.

T24 requires a representative soak run below set limits, with no OOM, no
uncontrolled swap and archived metrics. `factory.operations.soak` enforces the
limits it is *configured* with; this wrapper additionally enforces them with
systemd scope properties and records the cgroup's actual `memory.max` and
`cpu.max` in the archived report, so the run is attributable to a measured
constraint rather than an asserted one.

The limit probe and the soak run inside the same scope, so the recorded limits
cover the whole workload rather than a preliminary process.

Scope is unchanged: synthetic fixture only. This is not VPS equivalence, not
historical validation and not market validation.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEFAULT_MEMORY_MAX = "8G"
DEFAULT_CPU_QUOTA = "400%"

# Runs inside the scope: records the limits the kernel actually applied, then
# runs the soak in the same process so those limits cover the workload.
_PROBE = r"""
import json, sys
from pathlib import Path
def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as exc:
        return f"unavailable: {exc}"
cg = read("/proc/self/cgroup")
rel = cg.split("::", 1)[1] if "::" in cg else ""
base = Path("/sys/fs/cgroup") / rel.lstrip("/")
limits = {
    "cgroup_path": cg,
    "cgroup_root": str(base),
    "memory_max": read(base / "memory.max"),
    "memory_high": read(base / "memory.high"),
    "cpu_max": read(base / "cpu.max"),
    "swap_max": read(base / "memory.swap.max"),
}
Path(sys.argv[1]).write_text(json.dumps(limits, indent=2, sort_keys=True))
from factory.operations import soak
soak.run(
    sys.argv[2],
    iterations=int(sys.argv[3]),
    rows=int(sys.argv[4]),
    max_wall_seconds=int(sys.argv[5]),
)
"""


def _host_facts():
    facts = {}
    for name, command in (
        ("nproc", ["nproc"]),
        (
            "memory_total_bytes",
            ["sh", "-c", "awk '/MemTotal/{print $2*1024}' /proc/meminfo"],
        ),
        ("kernel", ["uname", "-r"]),
    ):
        try:
            facts[name] = subprocess.run(
                command, capture_output=True, text=True, check=True, timeout=30
            ).stdout.splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError) as exc:
            facts[name] = f"unavailable: {exc}"
    return facts


def run(
    output,
    iterations=10,
    rows=20000,
    memory_max=DEFAULT_MEMORY_MAX,
    cpu_quota=DEFAULT_CPU_QUOTA,
    max_wall_seconds=3600,
):
    """Run the soak inside an enforced systemd scope and archive the evidence."""
    if not Path("/usr/bin/systemd-run").exists() and not Path("/bin/systemd-run").exists():
        raise RuntimeError("systemd-run is required to enforce the soak limits")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    limits_path = output.with_suffix(".cgroup-limits.json")
    started = time.perf_counter()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    command = [
        "systemd-run",
        "--scope",
        "--quiet",
        "-p",
        f"MemoryMax={memory_max}",
        "-p",
        f"CPUQuota={cpu_quota}",
        "-p",
        "MemorySwapMax=0",
        "--",
        sys.executable,
        "-c",
        _PROBE,
        str(limits_path),
        str(output),
        str(iterations),
        str(rows),
        str(max_wall_seconds),
    ]
    probe = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=max_wall_seconds + 300,
        env=env,
    )
    if probe.returncode:
        raise RuntimeError(f"enforced soak failed: {probe.stderr.strip() or probe.stdout.strip()}")
    limits = json.loads(limits_path.read_text())
    report = json.loads(output.read_text())
    report["enforcement"] = {
        "mechanism": "systemd-run --scope",
        "requested": {
            "MemoryMax": memory_max,
            "CPUQuota": cpu_quota,
            "MemorySwapMax": "0",
        },
        "observed": limits,
        "host": _host_facts(),
        "wall_seconds_including_probe": time.perf_counter() - started,
    }
    from factory.data import atomic_bytes

    atomic_bytes(output, json.dumps(report, indent=2, sort_keys=True).encode())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="reports/soak/enforced-soak-report.json")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--memory-max", default=DEFAULT_MEMORY_MAX)
    parser.add_argument("--cpu-quota", default=DEFAULT_CPU_QUOTA)
    parser.add_argument("--max-wall-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    report = run(
        args.output,
        iterations=args.iterations,
        rows=args.rows,
        memory_max=args.memory_max,
        cpu_quota=args.cpu_quota,
        max_wall_seconds=args.max_wall_seconds,
    )
    summary = {
        k: report[k]
        for k in (
            "status",
            "iterations_completed",
            "rows_per_iteration",
            "peak_rss_bytes_sampled",
            "within_limits",
            "oom_detected",
            "uncontrolled_swap",
        )
    }
    summary["enforcement"] = report["enforcement"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report["within_limits"] and not report["oom_detected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
