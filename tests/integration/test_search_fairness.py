"""Search fairness: no eligible protocol is starved while the queue has work."""

from factory.exploration.persistent import Search, SearchProtocol
from factory.operations.fixtures import seed


def register(tmp_path, store, instrument, timeframe, seed_value):
    payload = seed(tmp_path, 240)
    protocol = SearchProtocol(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=payload["contract"]["windows"][0],
        family="momentum",
        timeframe=timeframe,
        code_revision=payload["contract"]["code_revision"],
        seed=seed_value,
        max_trials=1,
    )
    identity = Search(store, tmp_path).register(protocol)
    Search(store, tmp_path).ask(identity)
    return identity


def test_fair_pending_does_not_starve_a_protocol(tmp_path):
    store = None
    from factory.experiments import Store

    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    first = register(tmp_path, store, "EURUSD", "M1", 1)
    second = register(tmp_path, store, "GBPUSD", "M1", 2)
    # The first protocol has already produced its outcome; the second has not.
    store.pause(False, "test")
    search.enqueue_pending()
    from apps.coordinator.service import cycle

    assert cycle(store, tmp_path)
    search.feedback()
    pending = search.fair_pending()
    assert pending, "expected a pending trial"
    # The starved protocol's pending trial is scheduled ahead of the one that
    # has already produced an outcome.
    produced = {
        row["protocol_hash"]: row["n"]
        for row in store.rows(
            "SELECT t.protocol_hash, count(*) n FROM search_outcomes o "
            "JOIN search_trials t USING(trial_id) GROUP BY t.protocol_hash"
        )
    }
    assert produced.get(first, 0) >= 1
    assert pending[0]["protocol_hash"] == second


def test_fair_pending_is_stable_for_equal_production(tmp_path):
    from factory.experiments import Store

    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    one = register(tmp_path, store, "EURUSD", "M1", 11)
    two = register(tmp_path, store, "GBPUSD", "M1", 12)
    first = [row["protocol_hash"] for row in search.fair_pending()]
    second = [row["protocol_hash"] for row in search.fair_pending()]
    # With equal production the order falls back to arrival and is deterministic.
    assert first == second
    assert sorted(first) == sorted([one, two])
