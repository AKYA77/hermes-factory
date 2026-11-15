"""Explicitly generated monotone software reference, NOT market profitability.

The path is designed to exercise successful protocol qualification with real
native orders. It can never populate historical validated leaderboards.
"""

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json

from apps.coordinator.service import cycle
from factory.contracts import Window, serialize
from factory.data import Catalog
from factory.experiments import Store
from factory.operations.fixtures import seed
from factory.validation.access import HoldoutSpec
from factory.validation.protocol import (
    ValidationProtocol,
    ValidationController,
    ValidationCriteria,
    ValidationEvidencePolicy,
)


def positive_reference(root):
    payload = seed(root, 1200)
    catalog = Catalog(root / "catalog")
    template = list(catalog.read(payload["contract"]["dataset_hash"]))
    parts = []
    for quarter, (year, month) in enumerate(
        ((2025, 1), (2025, 4), (2025, 7), (2025, 10), (2026, 1), (2026, 4))
    ):
        start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp()) * 10**9
        data = [
            replace(
                q,
                event_ts_utc_ns=start + n * 60 * 10**9,
                bid_int=110000 + (quarter * len(template) + n) * 50,
                ask_int=110010 + (quarter * len(template) + n) * 50,
                ingest_batch_id="generated-positive-quarter-" + str(quarter),
            )
            for n, q in enumerate(template)
        ]
        m = catalog.commit(
            data,
            serialize([asdict(q) for q in data]).encode(),
            {
                "source": "GENERATED monotone software reference, not historical market observations",
                "license": "project test fixture",
                "synthetic": True,
            },
        )
        parts.append(m["dataset_hash"])
        if quarter == 0:
            first = start
        if quarter == 5:
            final_start = start
        end = data[-1].event_ts_utc_ns + 1
    view = catalog.compose(parts)
    return ValidationProtocol(
        schema_version="scientific-validation/v3",
        holdout=HoldoutSpec(
            dataset_hash=view["dataset_hash"],
            profile=payload["profile"],
            window=Window(start_ns=final_start, end_ns=end, role="final_holdout_unseen"),
            code_revision=payload["contract"]["code_revision"],
            external_use_declaration="NO_PRIOR_USE_DECLARED",
            declaration_notes="Fresh GENERATED reference fixture; no actual market performance claim",
        ),
        evidence_policy=ValidationEvidencePolicy(
            max_censored_fraction=0.1,
            max_marked_drawdown=".95",
            min_neighbor_closed_trades=50,
            min_neighbor_acceptable_fraction=0.5,
        ),
        start_ns=first,
        family="breakout",
        timeframe="M1",
        seed=42,
        trials_per_refit=1,
        cpu_seconds_per_refit=300,
        purge_seconds=86400,
        embargo_seconds=0,
        criteria=ValidationCriteria(
            min_oos_closed_trades=50,
            min_full_folds=2,
            min_annual_closed_trades=50,
            min_wilson_lower=0.5,
            min_net_profit=0,
            max_losing_streak=5,
            familywise_alpha=0.05,
            min_neighborhoods_with_trades=1,
            require_research_targets=True,
        ),
    )


def test_successful_cross_year_native_validation_is_reference_only(tmp_path):
    protocol = positive_reference(tmp_path)
    store = Store(tmp_path / "factory.sqlite")
    identity = ValidationController(store, tmp_path).register(protocol)
    store.pause(False, "generated-reference-test")
    for _ in range(80):
        cycle(Store(tmp_path / "factory.sqlite"), tmp_path, timeout=120)
        rows = store.rows(
            "SELECT report_json FROM validation_protocol_reports WHERE protocol_id=?", (identity,)
        )
        if rows:
            break
    assert rows
    report = json.loads(rows[0]["report_json"])
    assert report["status"] == "VALIDATED_REFERENCE", report
    assert report["synthetic"] is True and report["independently_validated"] is True
    assert report["eligible_for_historical_validated_board"] is False
    assert len(store.rows("SELECT * FROM holdout_consumptions")) == 1
    years = {
        datetime.fromtimestamp(
            r["result"]["windows"][0]["window"]["start_ns"] // 10**9, timezone.utc
        ).year
        for r in report["annual"]
    }
    assert years == {2025, 2026}
    assert len(report["annual"]) == 2
    assert len(report["folds"]) >= 2
    assert report["protocol_qualified"] is True
