#!/usr/bin/env python3
"""Measure the Rust engine against the Nautilus-backed Python reference.

Fairness rules this script enforces rather than assumes:

* Both engines receive the **same** generated case -- identical quotes, signals,
  profile, spec, conservative flag and finite-book configuration -- through the
  shared ``generate_case`` helper. There is no hand-built argument list.
* Both are run in-process/subprocess isolation per case, so one engine's caches
  cannot warm the other within a measurement.
* Reported numbers are **raw measurements only**. The script deliberately does
  NOT compute or print a speedup ratio: combining harness overhead with engine
  time would misrepresent isolated execution, which is the failure mode the
  owner directive calls out.

Envelope honesty: this host cannot enforce the target 4-vCPU / 8-GiB quota
(cgroup v2 controllers are not delegated), so results are measured on the
unrestricted VPS capacity and the report says so. They must not be presented as
target-envelope results.

    env -u PYTHONPATH .venv/bin/python scripts/benchmark_raptor_vs_reference.py \
        --cases 12 --workload medium
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import resource
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factory.simulation.runner import replay  # noqa: E402

import raptor_cases as cases  # noqa: E402
from parity_raptor_engine import INSTRUMENTS, generate_case  # noqa: E402

# Workload sizes expressed as generated case counts per instrument, so small,
# medium and large differ in total quotes processed rather than in engine knobs.
WORKLOADS = {"small": 4, "medium": 12, "large": 32}


def measure_python(profile, spec, quotes, signals, fill_model) -> dict:
    before_cpu = resource.getrusage(resource.RUSAGE_SELF)
    start = time.perf_counter()
    result = replay(quotes, profile, spec, signals, True, fill_model=fill_model)
    elapsed = time.perf_counter() - start
    after_cpu = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "wall_seconds": round(elapsed, 6),
        "cpu_seconds": round(after_cpu.ru_utime - before_cpu.ru_utime, 6),
        "trades": len(result["trades"]),
        "fills": len(result["fills"]),
        "quotes": len(quotes),
    }


def measure_rust(request: dict) -> dict:
    import tempfile

    binary = (
        Path(__file__).resolve().parent.parent
        / "rust"
        / "raptor-engine"
        / "target"
        / "release"
        / "raptor-engine"
    )
    # The engine reads the request from a file path, matching its CLI contract.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(request, handle)
        request_path = handle.name
    try:
        start = time.perf_counter()
        completed = subprocess.run([str(binary), request_path], capture_output=True, check=False)
        elapsed = time.perf_counter() - start
    finally:
        Path(request_path).unlink(missing_ok=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode()[:200])
    out = completed.stdout
    cpu = None
    try:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = round(usage.ru_utime + usage.ru_stime, 6)
    except Exception:  # pragma: no cover - platform dependent
        cpu = None
    parsed = json.loads(out)
    return {
        "wall_seconds": round(elapsed, 6),
        "cpu_seconds_children_including_prior": cpu,
        "trades": len(parsed["trades"]),
        "fills": len(parsed["fills"]),
        "quotes": len(request["quotes"]),
        "_note": "wall includes process start-up; RSS requires the GNU time wrapper "
        "and is reported separately by scripts/benchmark.sh",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=int,
        default=None,
        help="cases per instrument (defaults to the workload size)",
    )
    parser.add_argument("--workload", choices=sorted(WORKLOADS), default="medium")
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--instrument", default="all")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    per_instrument = args.cases if args.cases is not None else WORKLOADS[args.workload]
    instruments = INSTRUMENTS if args.instrument == "all" else [args.instrument]
    rng = random.Random(args.seed)

    rows = []
    for instrument in instruments:
        for index in range(per_instrument):
            profile, spec, quotes, signals, partial, fill_model = generate_case(rng, instrument)
            request = cases.build_request(profile, spec, quotes, signals, True, partial)
            py = measure_python(profile, spec, quotes, signals, fill_model)
            rs = measure_rust(request)
            # Sanity: the two engines must agree on trade/fill counts before any
            # timing is reported, otherwise the comparison is meaningless.
            if py["trades"] != rs["trades"] or py["fills"] != rs["fills"]:
                raise SystemExit(
                    f"engine disagreement on {instrument} case {index}: "
                    f"python trades={py['trades']} fills={py['fills']} vs "
                    f"rust trades={rs['trades']} fills={rs['fills']}"
                )
            rows.append(
                {
                    "instrument": instrument,
                    "case": index,
                    "quotes": py["quotes"],
                    "python": {k: v for k, v in py.items() if k != "quotes"},
                    "rust": {k: v for k, v in rs.items() if k not in ("quotes", "_note")},
                }
            )
            print(
                f"{instrument} case {index}: quotes={py['quotes']} "
                f"python_wall={py['wall_seconds']:.4f}s rust_wall={rs['wall_seconds']:.4f}s"
            )

    report = {
        "schema_version": "raptor-vs-reference-benchmark/v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": args.seed,
        "workload": args.workload,
        "cases_per_instrument": per_instrument,
        "instruments": instruments,
        "methodology": {
            "engine_inputs": "identical generated quotes, signals, profile, spec, "
            "conservative=True and finite-book configuration via "
            "scripts/parity_raptor_engine.generate_case",
            "python_timing": "wall via perf_counter around an in-process replay(); "
            "CPU via RUSAGE_SELF user-time delta",
            "rust_timing": "wall around a fresh subprocess of target/release/"
            "raptor-engine; the binary path is resolved relative to "
            "this script",
            "agreement_gate": "trade and fill counts must match exactly before timings "
            "are recorded; a mismatch aborts the run",
            "speedup_ratio_reported": False,
            "speedup_note": "No ratio is computed. Python wall time includes "
            "interpreter-side harness overhead that the Rust "
            "subprocess does not pay, and Rust wall time includes "
            "process start-up, so neither number isolates engine "
            "execution.",
        },
        "envelope": {
            "target": "4 vCPU / 8 GiB",
            "enforced": False,
            "reason": "cgroup v2 controllers are not delegated on this host; "
            "systemd-run --scope -p CPUQuota=400% -p MemoryMax=8G reports "
            "CPUQuotaPerSecUSec=infinity and MemoryMax=infinity",
            "measured_on": "unrestricted VPS capacity; these are NOT target-envelope results",
        },
        "synthetic_only": True,
        "synthetic_note": "Generated quote streams, not acquired history; these "
        "numbers must not be extrapolated to historical throughput.",
        "rows": rows,
    }

    text = json.dumps(report, indent=1)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
        print(f"\nwrote {args.output}")
    else:
        print("\n" + text[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
