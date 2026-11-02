"""Explicitly synthetic deterministic quote paths, never historical data."""

from datetime import datetime, timezone
import math
from pathlib import Path
from factory.contracts import ExperimentContract, Signal, StrategySpec, Window, fingerprint
from factory.data import Catalog, Quote
from factory.instruments import synthetic_profile


def seed(root, rows=2000):
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    quotes = []
    for i in range(rows):
        bid = 110000 + int(220 * math.sin(i / 12))
        quotes.append(
            Quote(
                "EURUSD",
                start + i * 60 * 10**9,
                bid,
                bid + 10,
                100000,
                "synthetic-sine/v1",
                "seed-v1",
                i,
                source_precision="minute-fixture",
            )
        )
    raw = "\n".join(f"{q.event_ts_utc_ns},{q.bid_int},{q.ask_int}" for q in quotes).encode()
    manifest = Catalog(Path(root) / "catalog").commit(
        quotes,
        raw,
        {
            "source": "project-generated synthetic sine fixture/v1",
            "license": "project test data only",
            "synthetic": True,
        },
    )
    spec = StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=3, threshold="1"),
        stop_ticks=60,
    )
    profile = synthetic_profile("EURUSD")
    import subprocess

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    contract = ExperimentContract(
        strategy_hash=spec.strategy_hash,
        dataset_hash=manifest["dataset_hash"],
        instrument_hash=fingerprint(profile),
        engine_version="1.231.0",
        code_revision=revision,
        fill_version="adverse-fill/v1",
        evaluation_policy="synthetic-training/v1",
        scenario="historical-pessimistic/v1",
        windows=(Window(start_ns=start, end_ns=quotes[-1].event_ts_utc_ns + 1, role="train_only"),),
        seed=123,
    )
    return {
        "strategy": spec.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
    }
