"""Diversity-aware descriptive shortlist selection."""

import pytest

from factory.contracts import fingerprint
from factory.data import sha256
from factory.ranking.qualified import (
    ATTESTATION,
    QualifiedRanking,
    QualifiedRankingRequest,
    select_diverse,
)
from test_improvement import parent_run


def ranked(identifier, operator, timeframe):
    return {
        "strategy_id": identifier,
        "operator": operator,
        "timeframe": timeframe,
        "status": "SIMULATED",
        "metrics": {},
    }


def test_diversity_guard_limits_repeated_operator_and_timeframe():
    candidates = [
        ranked("a", "momentum", "M1"),
        ranked("b", "momentum", "M1"),
        ranked("c", "momentum", "M1"),
        ranked("d", "breakout", "H1"),
        ranked("e", "trend", "H4"),
    ]
    selected, skipped, counts = select_diverse(candidates, max_slots=3, per_key_limit=1)
    assert len(selected) == 3
    assert len({(c["operator"], c["timeframe"]) for c in selected}) == 3
    assert [s["strategy_id"] for s in skipped] == ["b", "c"]
    assert all(entry["reason"] == "DIVERSITY_LIMIT" for entry in skipped)
    assert counts == {"momentum|M1": 1, "breakout|H1": 1, "trend|H4": 1}


def test_slot_limit_is_reported_separately_from_diversity():
    candidates = [ranked("a", "momentum", "M1"), ranked("b", "breakout", "H1")]
    selected, skipped, counts = select_diverse(candidates, max_slots=1, per_key_limit=2)
    assert [c["strategy_id"] for c in selected] == ["a"]
    assert skipped == [
        {"strategy_id": "b", "operator": "breakout", "timeframe": "H1", "reason": "SLOT_LIMIT"}
    ]
    assert counts == {"momentum|M1": 1}


def test_qualified_ranking_report_is_descriptive_and_immutable(tmp_path):
    store, identity, parent = parent_run(tmp_path)
    service = QualifiedRanking(store, tmp_path)
    request = QualifiedRankingRequest(
        instrument="EURUSD",
        max_slots=5,
        per_key_limit=2,
        authorized_by="ranking acceptance",
        attestation=ATTESTATION,
    )
    report = service.report(request)
    assert report["descriptive_only"] is True
    assert report["qualification_authorized"] is False
    assert report["candidates_considered"] >= 1
    assert len(report["selected"]) <= 5
    assert report["selection_policy"] == "tier-then-diversity greedy shortlist"
    digest = fingerprint(report)
    path = tmp_path / "artifacts" / "qualified-ranking" / (digest + ".json")
    assert path.exists() and sha256(path) == digest
    assert fingerprint(service.report(request)) == digest
    with pytest.raises(ValueError, match="unknown instrument"):
        service.report(
            QualifiedRankingRequest(
                instrument="NOPE",
                authorized_by="ranking acceptance",
                attestation=ATTESTATION,
            )
        )
    with pytest.raises(ValueError, match="cannot exceed"):
        QualifiedRankingRequest(
            instrument="EURUSD",
            max_slots=1,
            per_key_limit=3,
            authorized_by="ranking acceptance",
            attestation=ATTESTATION,
        )
