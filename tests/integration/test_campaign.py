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


def test_changed_plan_does_not_enqueue_more_jobs(tmp_path):
    import pytest

    store = setup(tmp_path, 8)
    with pytest.raises(ValueError, match="plan differs"):
        setup(tmp_path, 9)
    assert len(store.rows("SELECT * FROM jobs")) == 8


def test_invalid_batch_size_is_rejected_before_setup(tmp_path):
    import pytest
    from factory.operations.campaign import campaign

    with pytest.raises(ValueError, match="batch size"):
        campaign(tmp_path, 8, 0)
    assert not (tmp_path / "factory.sqlite").exists()
