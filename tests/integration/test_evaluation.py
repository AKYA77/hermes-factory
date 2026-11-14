from factory.operations.fixtures import seed
from factory.validation.evaluate import evaluate


def test_frozen_separate_windows(tmp_path):
    payload = seed(tmp_path, 240)
    original = payload["contract"]["windows"][0]
    mid = (original["start_ns"] + original["end_ns"]) // 2
    payload["contract"]["windows"] = [
        {"start_ns": original["start_ns"], "end_ns": mid, "role": "train_only"},
        {"start_ns": mid, "end_ns": original["end_ns"], "role": "selection_oos"},
    ]
    result = evaluate(tmp_path / "catalog", payload)
    assert len(result["windows"]) == 2
    for w in result["windows"]:
        assert w["replay"]["quote_count"] > 0
        assert w["metrics"]["completed_trades"] > 0
        assert all(t["entry_fill"]["ts"] >= w["window"]["start_ns"] for t in w["replay"]["trades"])
        assert all(t["exit_fill"]["ts"] < w["window"]["end_ns"] for t in w["replay"]["trades"])
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
