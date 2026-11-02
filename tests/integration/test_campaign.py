from factory.operations.campaign import setup, batch, verify


def test_campaign_keeps_infeasible_strategies_honest(tmp_path):
    store = setup(tmp_path, 8)
    assert batch(tmp_path, 8) > 0
    checks = verify(tmp_path)
    assert checks["completed_replays"] == 8
    assert not checks["assertion_failures"]
    assert len(checks["zero_trade_runs"]) == 8
    assert checks["totals"]["skipped_opportunities"] > 0
    setup(tmp_path, 8)
    assert len(store.rows("SELECT * FROM jobs")) == 8
