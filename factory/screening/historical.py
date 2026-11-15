"""Admission-bound training diagnostics; never pruning or native result mutation."""

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import Field

from factory.contracts import (
    Contract,
    ExperimentContract,
    InstrumentSpec,
    StrategySpec,
    fingerprint,
    serialize,
)
from factory.data import Catalog, atomic_bytes, sha256
from factory.data.admission import InputRegistry, require_active_at_completion
from factory.experiments import Store
from factory.exploration.discovery import require_training_scope
from factory.features.disk import BarCache
from factory.features.indicators import compiler_events
from factory.provenance import execution_revision
from factory.screening.labels import CostHorizonPolicy, estimate_labels

ATTESTATION = "Authorize training-only feature diagnostics and mandatory native evidence; no approximate pruning"


class HistoricalShadowRequest(Contract):
    schema_version: Literal["historical-shadow-diagnostics/v1"] = "historical-shadow-diagnostics/v1"
    experiment_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile: InstrumentSpec
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]


def diagnose(root, request):
    root = Path(root)
    request = HistoricalShadowRequest.model_validate(request)
    store = Store(root / "factory.sqlite")
    rows = store.rows(
        "SELECT * FROM experiments WHERE experiment_hash=?", (request.experiment_hash,)
    )
    if not rows:
        raise ValueError("retained native experiment required")
    row = rows[0]
    contract = ExperimentContract.model_validate_json(row["contract_json"])
    spec = StrategySpec.model_validate_json(
        store.rows(
            "SELECT spec_json FROM strategy_specs WHERE strategy_id=?", (row["strategy_id"],)
        )[0]["spec_json"]
    )
    result = json.loads(row["result_json"])
    profile = request.profile
    if profile.synthetic or result.get("synthetic") is not False:
        raise ValueError("historical admission required; generated evidence cannot be relabeled")
    if (
        contract.code_revision != execution_revision()
        or fingerprint(profile) != contract.instrument_hash
    ):
        raise ValueError("historical diagnostic code/profile mismatch")
    if len(contract.windows) != 1 or contract.windows[0].role != "train_only":
        raise ValueError("historical diagnostics require one training window")
    native = root / "artifacts" / (contract.experiment_hash + ".json")
    if (
        native.is_symlink()
        or sha256(native) != row["artifact_hash"]
        or fingerprint(result) != row["artifact_hash"]
    ):
        raise ValueError("native artifact integrity mismatch")
    catalog = Catalog(root / "catalog")
    registry = InputRegistry(root, catalog)
    admission = registry.require(contract, profile)
    policy = CostHorizonPolicy()
    identity = fingerprint(
        {"request": request, "native_artifact_hash": row["artifact_hash"], "policy": policy}
    )

    def guard(db):
        require_active_at_completion(db, contract, result, catalog.root)
        require_training_scope(db, SimpleNamespace(profile=profile, window=contract.windows[0]))

    with store.transaction() as db:
        guard(db)
        if not db.execute(
            "SELECT 1 FROM audit_events WHERE action='historical_shadow_started' AND json_extract(payload,'$.diagnostic_id')=?",
            (identity,),
        ).fetchone():
            store._audit(
                db,
                request.authorized_by,
                "historical_shadow_started",
                {
                    "diagnostic_id": identity,
                    "request": request.model_dump(mode="json"),
                    "native_artifact_hash": row["artifact_hash"],
                },
            )
    window = contract.windows[0]
    bars = BarCache(root / "cache" / "historical-shadow-bars")
    with compiler_events(
        bars,
        catalog,
        contract.dataset_hash,
        contract.instrument_hash,
        contract.code_revision,
        spec,
        start_ns=window.start_ns,
        end_ns=window.end_ns,
    ) as (events, lookup):
        estimate = estimate_labels(events, spec, profile, contract, policy, transform_lookup=lookup)
    catalog.verify(contract.dataset_hash, deep=True)
    if (
        registry.require(contract, profile) != admission
        or contract.code_revision != execution_revision()
    ):
        raise ValueError("historical diagnostic scope changed")
    marked = Decimal(result["equity"]["ending_marked_equity"])
    positive = bool(
        result["trades"]
        and marked > contract.initial_equity
        and not result["equity"]["insolvent_at_any_observation"]
    )
    body = {
        "schema_version": request.schema_version,
        "diagnostic_id": identity,
        "request": request.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
        "input_admission": admission,
        "native_artifact_hash": row["artifact_hash"],
        "estimate": estimate,
        "estimate_hash": fingerprint(estimate),
        "native_positive_marked_with_closed_trades": positive,
        "observed_false_negative": bool(estimate["rejection_suggested"] and positive),
        "approximate_pruning_authorized": False,
        "scope": "Posthoc training diagnostics only; not prospective independent calibration, OOS or strategy qualification",
    }
    path = root / "artifacts" / "historical-shadow" / f"{identity}.json"
    with store.transaction() as db:
        guard(db)
        if sha256(native) != row["artifact_hash"]:
            raise ValueError("native artifact changed during diagnostics")
        encoded = serialize(body).encode()
        if path.exists() and path.read_bytes() != encoded:
            raise ValueError("immutable historical diagnostic conflict")
        atomic_bytes(path, encoded)
        if not db.execute(
            "SELECT 1 FROM audit_events WHERE action='historical_shadow_completed' AND json_extract(payload,'$.diagnostic_id')=?",
            (identity,),
        ).fetchone():
            store._audit(
                db,
                request.authorized_by,
                "historical_shadow_completed",
                {
                    "diagnostic_id": identity,
                    "artifact_hash": fingerprint(body),
                    "estimate_hash": body["estimate_hash"],
                    "native_artifact_hash": row["artifact_hash"],
                },
            )
    return body
