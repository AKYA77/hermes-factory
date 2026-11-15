"""Descriptive cohort aggregation from retained verified training results."""

from decimal import Decimal as D
import hashlib
import json

import pytest

from factory.diagnostics.cohorts import (
    ATTESTATION,
    DiagnosticCohortRequest,
    DiagnosticCohorts,
    aggregate,
    session_label,
)
from factory.contracts import fingerprint
from factory.data import sha256
from test_historical_cohorts import prepared


def test_session_buckets_are_declared_utc_hour_ranges():
    assert session_label(0, (("ASIA", 0, 7),)) == "ASIA"
    assert session_label(7 * 3600 * 10**9, (("ASIA", 0, 7), ("EUROPE", 7, 14))) == "EUROPE"
    assert session_label(23 * 3600 * 10**9, (("ASIA", 0, 7),)) == "OFFSHORE"


def test_aggregate_reports_descriptive_cohorts_without_qualifying():
    result = {
        "ending_equity": "1010",
        "trades": [
            {
                "side": "BUY",
                "entry_fill": {"ts": 1 * 3600 * 10**9, "price": "1.10000"},
                "exit_fill": {"ts": 2 * 3600 * 10**9, "price": "1.10100"},
                "diagnostic": {
                    "status": "MEASURED",
                    "tags": ["FAST_STOP"],
                    "mfe_r": "0.1",
                    "mae_r": "-1.0",
                },
            },
            {
                "side": "SELL",
                "entry_fill": {"ts": 8 * 3600 * 10**9, "price": "1.10100"},
                "exit_fill": {"ts": 9 * 3600 * 10**9, "price": "1.10200"},
                "diagnostic": {"status": "MEASURED", "tags": [], "mfe_r": "0.2", "mae_r": "-1.0"},
            },
            {
                "side": "BUY",
                "entry_fill": {"ts": 3 * 3600 * 10**9, "price": "1.10000"},
                "exit_fill": {"ts": 4 * 3600 * 10**9, "price": "1.10050"},
                "diagnostic": {"status": "MEASURED", "tags": [], "mfe_r": "0.5", "mae_r": "-1.0"},
            },
        ],
        "equity": {"marked_equity_curve": ()},
    }
    body = aggregate(result)
    assert body["descriptive_only"] is True
    assert body["closed_trades"] == 3 and body["open_trades"] == 0
    assert body["sessions"]["ASIA"]["trades"] == 2
    assert body["sessions"]["EUROPE"]["trades"] == 1
    assert body["sides"]["BUY"]["wins"] == 2 and body["sides"]["SELL"]["losses"] == 1
    assert set(body["equity_regimes"]) <= {"PEAK", "DRAWDOWN", "RECOVERY"}
    assert sum(v["trades"] for v in body["equity_regimes"].values()) == 3
    assert body["max_losing_streak"] == 1
    assert body["stop_and_timeout_classes"] == {"FAST_STOP": 1}
    assert body["failure_pattern_groups"]["FAST_STOP"] == 1
    assert body["failure_pattern_groups"]["NO_TAGGED_FAILURE"] == 2
    assert body["excursions"]["mfe_r_mean"] == str((D("0.1") + D("0.2") + D("0.5")) / 3)
    assert float(body["hold_seconds"]["max"]) == 3600.0
    assert body["cost_sensitivity"]["measured"] is False
    assert "not strategy qualification" in body["limitations"][0]


def test_diagnostic_cohorts_api_is_authenticated(tmp_path):
    from fastapi.testclient import TestClient
    from apps.api.main import create_app

    store, request, calibration, prospective, admission = prepared(tmp_path)
    (tmp_path / "access.json").write_text(
        json.dumps(
            [
                {"role": role, "sha256": hashlib.sha256(("test-" + role).encode()).hexdigest()}
                for role in ("viewer", "operator")
            ]
        )
    )
    client = TestClient(create_app(tmp_path))
    payload = {
        "experiment_hash": calibration.experiment_hash,
        "authorized_by": "cohort diagnostics acceptance",
        "attestation": ATTESTATION,
    }
    assert client.post("/api/v1/research/diagnostic-cohorts", json=payload).status_code == 401
    response = client.post(
        "/api/v1/research/diagnostic-cohorts",
        json=payload,
        headers={"Authorization": "Bearer test-viewer"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["aggregate"]
    assert body["descriptive_only"] is True and body["closed_trades"] > 0
    assert body["cost_sensitivity"]["measured"] is False


def test_cohort_report_requires_retained_training_experiment(tmp_path):
    store, request, calibration, prospective, admission = prepared(tmp_path)
    service = DiagnosticCohorts(store, tmp_path)
    report = service.report(
        DiagnosticCohortRequest(
            experiment_hash=calibration.experiment_hash,
            authorized_by="cohort diagnostics acceptance",
            attestation=ATTESTATION,
        )
    )
    body = report["aggregate"]
    assert body["descriptive_only"] is True and body["closed_trades"] > 0
    assert 0 <= body["unresolved_trades"] <= body["closed_trades"]
    assert set(body["sides"]) <= {"BUY", "SELL"}
    assert report["volatility_regime_thresholds"] is not None
    assert report["volatility_regime_thresholds"]["window_minutes"] == 60
    regimes = body["volatility_regimes"]
    assert regimes and set(regimes) <= {"LOW", "NORMAL", "HIGH"}
    assert sum(entry["trades"] for entry in regimes.values()) <= body["closed_trades"]
    identity = fingerprint(report)
    path = tmp_path / "artifacts" / "cohorts" / (identity + ".json")
    assert path.exists() and sha256(path) == identity
    repeated = service.report(
        DiagnosticCohortRequest(
            experiment_hash=calibration.experiment_hash,
            authorized_by="cohort diagnostics acceptance",
            attestation=ATTESTATION,
        )
    )
    assert fingerprint(repeated) == identity
    with pytest.raises(ValueError, match="unknown experiment"):
        service.report(
            DiagnosticCohortRequest(
                experiment_hash="e" * 64,
                authorized_by="cohort diagnostics acceptance",
                attestation=ATTESTATION,
            )
        )
