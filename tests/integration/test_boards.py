"""Eight independent boards: five-slot cap, independence and retention."""

from factory.contracts import (
    ExperimentContract,
    Signal,
    StrategySpec,
    fingerprint,
    serialize,
)
from factory.data import atomic_bytes, sha256
from factory.ranking import leaderboard
from test_improvement import parent_run


def add_candidate(store, root, parent_row, index, instrument="EURUSD"):
    spec = StrategySpec(
        instrument=instrument,
        timeframe="M1",
        signal=Signal(operator="momentum", lookback=index + 2, threshold="1"),
        stop_ticks=60,
    )
    base = ExperimentContract.model_validate_json(parent_row["contract_json"])
    contract = base.model_copy(
        update={
            "strategy_hash": spec.strategy_hash,
            "instrument_hash": fingerprint(
                {
                    "instrument": instrument,
                    "version": "test/v1",
                    "tick_size": "0.00001",
                    "pip_size": "0.0001",
                    "price_scale": 100000,
                    "base_currency": instrument[:3],
                    "quote_currency": instrument[3:],
                    "contract_multiplier": "1",
                    "volume_step": "0.001",
                    "min_volume": "0.001",
                    "max_volume": "100000",
                    "margin_rate": "0.01",
                    "min_stop_ticks": 1,
                    "source": "test",
                    "synthetic": True,
                }
            ),
        }
    )
    run_id = f"{contract.experiment_hash}-{index}"
    result = {"trades": [], "ending_equity": "100", "synthetic": True}
    payload = root / "artifacts" / "experiments" / (run_id + ".json")
    atomic_bytes(payload, serialize(result).encode())
    store.register_strategy(spec)
    with store.transaction() as db:
        db.execute(
            "INSERT OR IGNORE INTO experiments VALUES(?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                run_id,
                spec.strategy_hash,
                instrument,
                serialize(contract),
                serialize(result),
                sha256(payload),
                "SIMULATED",
                float(index),
            ),
        )
    return spec.strategy_hash


def test_T16_board_caps_at_five_and_keeps_slots(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    for index in range(7):
        add_candidate(store, tmp_path, parent, index)
    board = leaderboard(store, "EURUSD")
    assert board["max_slots"] == 5
    assert len(board["candidates"]) == 5
    assert board["excluded_other_execution_runs"] == 0


def test_T16_boards_are_independent(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    for index in range(3):
        add_candidate(store, tmp_path, parent, index, "EURUSD")
    add_candidate(store, tmp_path, parent, 10, "GBPUSD")
    eur = leaderboard(store, "EURUSD")
    gbp = leaderboard(store, "GBPUSD")
    assert len(eur["candidates"]) == 4
    assert len(gbp["candidates"]) == 1
    assert {c["strategy_id"] for c in eur["candidates"]}.isdisjoint(
        {c["strategy_id"] for c in gbp["candidates"]}
    )


def test_T16_retention_is_below_seventy_percent(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    for index in range(10):
        add_candidate(store, tmp_path, parent, index)
    board = leaderboard(store, "EURUSD")
    assert len(board["candidates"]) == 5
    retained = len(board["candidates"]) / 11
    assert retained < 0.7
