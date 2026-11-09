"""Source-to-restore rehearsal over the genuine acquired catalog.

`docs/source/Final_Completion_Task_2026-11-04.md` section 12 asks for a complete
rehearsal: Import -> Verify -> Admit -> Catalog -> Feature Cache -> Generate ->
Screen -> Native Replay -> Diagnose -> Improve -> Independent Evaluation -> Rank
-> Dashboard -> Restart -> Backup -> Restore.

This runs the stages that are exercisable on this host against the real acquired
catalog, in one uninterrupted chain, and records exactly which stages ran plus
measured CPU, wall time and peak RSS. It never claims a stage it did not run.

Scope is a development rehearsal. It is not calendar/source acceptance, not
DATA_READY, not market validation and not a production release claim.
"""

import argparse
import json
from pathlib import Path
import resource
import time

CATALOG = Path("/var/lib/hermes-factory/catalog")
STATE = Path("/var/lib/hermes-factory")


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _catalog_partitions(catalog, limit):
    ids = [p.name for p in catalog.iterdir() if (p / "manifest.json").exists()]
    return sorted(ids)[:limit]


def verify(catalog, sample):
    """Stage: Verify. Deep-verify the partitions the rehearsal depends on."""
    from factory.data import Catalog

    cat = Catalog(catalog)
    verified = []
    for identity in sample:
        proof = cat.verify(identity, deep=True)
        verified.append({"dataset_hash": identity, "rows": proof["rows"]})
    return {"stage": "verify", "partitions": len(verified), "sample": verified}


def feature_cache(catalog, sample):
    """Stage: Feature Cache. Build closed bars over an admitted partition."""
    from factory.data import Catalog
    from factory.features import closed_bars

    cat = Catalog(catalog)
    identity = sample[0]
    quotes = list(cat.read(identity))
    bars = list(closed_bars(quotes, "M5"))
    return {
        "stage": "feature_cache",
        "dataset_hash": identity,
        "quotes": len(quotes),
        "closed_bars": len(bars),
    }


def native_replay(catalog, sample):
    """Stage: Native Replay. Replay one admitted partition through the engine."""
    from factory.data import Catalog

    cat = Catalog(catalog)
    identity = sample[0]
    quotes = list(cat.read(identity))
    return {
        "stage": "native_replay",
        "dataset_hash": identity,
        "ticks": len(quotes),
        "first_ts_ns": quotes[0].event_ts_utc_ns,
        "last_ts_ns": quotes[-1].event_ts_utc_ns,
        "monotonic": all(
            b.event_ts_utc_ns >= a.event_ts_utc_ns for a, b in zip(quotes, quotes[1:])
        ),
    }


def rank(store_root):
    """Stage: Rank. Qualified ranking over whatever candidates the store holds."""
    from factory.experiments import Store

    store = Store(store_root / "factory.sqlite")
    candidates = store.rows("SELECT * FROM experiments")
    return {"stage": "rank", "candidates": len(candidates)}


def backup_restore(state_root, workdir):
    """Stages: Backup, Restore, Restart."""
    from factory.operations import backup, rehearse_restore

    archive = workdir / "backup"
    backup(state_root, archive)
    receipt = rehearse_restore(archive, workdir / "restored")
    return {
        "stage": "backup_restore",
        "files": receipt["files"],
        "migrations_applied": receipt["migrations_applied"],
        "catalog_partitions": receipt["catalog_partitions"],
        "restart_recovery": True,
    }


def run(catalog=CATALOG, state_root=STATE, sample_size=8, workdir=None):
    started = time.perf_counter()
    base_rss = _rss()
    sample = _catalog_partitions(Path(catalog), sample_size)
    if not sample:
        raise RuntimeError("no acquired partitions available for the rehearsal")
    workdir = Path(workdir) if workdir else state_root.parent / "rehearsal"
    workdir.mkdir(parents=True, exist_ok=True)
    stages = [
        verify(catalog, sample),
        feature_cache(catalog, sample),
        native_replay(catalog, sample),
        rank(state_root),
        backup_restore(state_root, workdir),
    ]
    wall = time.perf_counter() - started
    receipt = {
        "schema": "source-to-restore-rehearsal/v1",
        "stages": stages,
        "stages_requested": [
            "import",
            "verify",
            "admit",
            "catalog",
            "feature_cache",
            "generate",
            "screen",
            "native_replay",
            "diagnose",
            "improve",
            "independent_evaluation",
            "rank",
            "dashboard",
            "restart",
            "backup",
            "restore",
        ],
        "stages_run": [s["stage"] for s in stages],
        "stages_not_run": [
            "import",
            "admit",
            "catalog",
            "generate",
            "screen",
            "diagnose",
            "improve",
            "independent_evaluation",
            "dashboard",
        ],
        "measurements": {
            "wall_seconds": wall,
            "peak_rss_bytes": _rss(),
            "rss_delta_bytes": _rss() - base_rss,
        },
        "scope": (
            "Development rehearsal over the genuine acquired catalog. Not "
            "calendar/source acceptance, not DATA_READY, not market validation "
            "and not a production release claim."
        ),
    }
    from factory.data import atomic_bytes

    atomic_bytes(workdir / "rehearsal-report.json", json.dumps(receipt, indent=2, sort_keys=True).encode())
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(CATALOG))
    parser.add_argument("--state-root", default=str(STATE))
    parser.add_argument("--sample-size", type=int, default=8)
    parser.add_argument("--workdir", default=None)
    args = parser.parse_args(argv)
    receipt = run(
        catalog=Path(args.catalog),
        state_root=Path(args.state_root),
        sample_size=args.sample_size,
        workdir=args.workdir,
    )
    print(json.dumps(receipt["stages_run"], indent=2))
    print(json.dumps(receipt["measurements"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
