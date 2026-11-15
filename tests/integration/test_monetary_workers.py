"""Cross-currency native training + irreversible confirmation, offline fixtures."""

from dataclasses import replace, asdict
from decimal import Decimal as D
import json

from apps.coordinator.worker import run
from apps.coordinator.service import cycle
from factory.contracts import ExperimentContract, StrategySpec, Window, fingerprint, serialize
from factory.data import Catalog
from factory.experiments import Store
from factory.instruments import synthetic_profile
from factory.operations.fixtures import seed
from factory.validation.access import HoldoutSpec, Holdouts


def test_jpy_many_trade_training_and_frozen_confirmation_with_dated_conversion(tmp_path):
    payload = seed(tmp_path, 480)
    catalog = Catalog(tmp_path / "catalog")
    data = [
        replace(
            q, instrument_id="USDJPY", price_scale=1000, ingest_batch_id="jpy-software-reference"
        )
        for q in catalog.read(payload["contract"]["dataset_hash"])
    ]
    manifest = catalog.commit(
        data,
        serialize([asdict(q) for q in data]).encode(),
        {
            "source": "synthetic JPY conversion software fixture",
            "synthetic": True,
            "license": "project test fixture",
        },
    )
    profile = synthetic_profile("USDJPY")
    spec = StrategySpec.model_validate({**payload["strategy"], "instrument": "USDJPY"})
    cut = data[240].event_ts_utc_ns
    full = payload["contract"]["windows"][0]
    contract = ExperimentContract.model_validate(
        {
            **payload["contract"],
            "dataset_hash": manifest["dataset_hash"],
            "instrument_hash": fingerprint(profile),
            "strategy_hash": spec.strategy_hash,
            "windows": [{**full, "end_ns": cut}],
        }
    )
    holdouts = Holdouts(tmp_path)
    holdout_id = holdouts.register(
        HoldoutSpec(
            dataset_hash=manifest["dataset_hash"],
            profile=profile,
            code_revision=contract.code_revision,
            window=Window(start_ns=cut, end_ns=full["end_ns"], role="final_holdout_unseen"),
            external_use_declaration="NO_PRIOR_USE_DECLARED",
            declaration_notes="Fresh synthetic software input; no historical market claim",
        )
    )
    training = {
        "strategy": spec.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
    }
    result = run(training, tmp_path)
    store = Store(tmp_path / "factory.sqlite")
    store.complete_experiment(contract, spec, result["result"], result["artifact_hash"])
    native = result["result"]
    assert len(native["trades"]) >= 3 and not native["integrity_errors"]
    assert native["reconciliation"]["native_reference_status"] == "VERIFIED"
    if not native["open_trade"]:
        assert D(native["equity"]["ending_marked_equity"]) == D(native["ending_equity"])
    holdouts.freeze(holdout_id, contract.experiment_hash)
    holdouts.enqueue(holdout_id)
    store.pause(False, "software test")
    assert cycle(store, tmp_path)
    evaluation = store.rows("SELECT * FROM evaluation_results")
    assert len(evaluation) == 1
    evidence = json.loads(evaluation[0]["result_json"])
    assert evidence["synthetic"] and evidence["status"] == "INSUFFICIENT_EVIDENCE"
    confirm = evidence["windows"][0]["replay"]
    assert len(confirm["trades"]) >= 3 and not confirm["integrity_errors"]
    assert confirm["reconciliation"]["native_reference_status"] == "VERIFIED"
    assert all(f["conversion_ts"] == f["ts"] for f in confirm["fills"])
    assert Holdouts(tmp_path).status()[0]["status"] == "HOLDOUT_CONSUMED"
