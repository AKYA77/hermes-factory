from factory.experiments import Store
from factory.exploration import propose
from factory.contracts import ExperimentContract, Window, fingerprint
from factory.simulation.runner import replay
from conftest import quotes


def test_proposal_coverage_and_seed(tmp_path):
    a = Store(tmp_path / "a")
    b = Store(tmp_path / "b")
    first = list(propose(a, 42, budget=8))
    second = list(propose(b, 42, budget=8))
    assert [s.strategy_hash for s, _ in first] == [s.strategy_hash for s, _ in second]
    dimensions = {(s.instrument, s.signal.operator, s.timeframe) for s, _ in first}
    assert len(dimensions) == 8
    assert len({s.instrument for s, _ in first}) == 8
    assert sum(r["proposals"] for r in a.rows("SELECT * FROM research_coverage")) == 8
    # This tests proposal-count coverage, not CPU-time fairness or all instruments.


def test_T25_window_change_identity(spec, profile):
    def make(end):
        return ExperimentContract(
            strategy_hash=spec.strategy_hash,
            dataset_hash="a" * 64,
            instrument_hash=fingerprint(profile),
            engine_version="1.231.0",
            code_revision="fixture",
            fill_version="adverse-fill/v1",
            evaluation_policy="test/v1",
            scenario="historical-pessimistic/v1",
            windows=(Window(start_ns=1, end_ns=end, role="selection_oos"),),
            seed=42,
        )

    assert make(10).experiment_hash != make(11).experiment_hash


def test_engine_exact_reproducibility(profile, spec):
    q = quotes([(110000, 110010), (110000, 110010), (110350, 110360), (110400, 110410)])
    signal = [{"available_at": q[0].event_ts_utc_ns, "side": "BUY"}]
    a = replay(q, profile, spec, signal, True)
    b = replay(q, profile, spec, signal, True)
    assert fingerprint(a) == fingerprint(b)
