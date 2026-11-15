"""Generated operator/search/chronology integration; no historical market claim."""

import json

import pytest
from pydantic import ValidationError

from factory.contracts import Signal, StrategySpec, fingerprint
from factory.data import Quote
from factory.experiments import Store
from factory.exploration.persistent import Search, SearchProtocol
from factory.operations.fixtures import seed
from factory.instruments import synthetic_profile
from factory.simulation.runner import replay
from factory.strategies import compile_signals
from factory.validation.protocol import ValidationProtocol, ValidationController, neighbors
from test_search import protocol
from test_scientific_protocol import protocol_fixture
from apps.coordinator.service import cycle


NEW_FAMILIES = ("trend", "reversal", "range", "volatility", "session", "confluence")


def choices(family):
    return {
        "components": ("trend", "momentum") if family == "confluence" else (),
        "session_hours": tuple(range(24)) if family == "session" else (),
    }


@pytest.mark.parametrize("family", NEW_FAMILIES)
def test_new_family_compiler_reaches_real_native_orders(family):
    levels = [
        110100,
        110000,
        109990,
        110000,
        110100,
        110200,
        110210,
        110200,
        110300,
        110200,
        110100,
        110200,
        110300,
        110400,
        110300,
        110200,
    ]
    quotes = []
    for i in range(64):
        width = 20 if i % 7 == 0 else 5
        for j, offset in enumerate((-width, width, 0)):
            bid = levels[i % len(levels)] + offset
            quotes.append(
                Quote(
                    "EURUSD",
                    1735689600 * 10**9 + i * 60 * 10**9 + j * 20 * 10**9,
                    bid,
                    bid + 10,
                    100000,
                    "generated-family-test",
                    "v1",
                    i * 3 + j,
                )
            )
    spec = StrategySpec(
        instrument="EURUSD",
        timeframe="M1",
        stop_ticks=100,
        signal=Signal(operator=family, version="2", lookback=3, threshold="1", **choices(family)),
    )
    signals = compile_signals(quotes, spec)
    assert signals, family
    result = replay(quotes, synthetic_profile("EURUSD"), spec, signals, True)
    assert result["fills"], (family, result["skips"])
    assert not result["integrity_errors"] and not result["rejections"]
    allowed = {s["available_at"] for s in signals}
    for trade in result["trades"]:
        assert trade["signal"]["available_at"] in allowed
        assert trade["entry_fill"]["ts"] > trade["signal"]["available_at"]


@pytest.mark.parametrize("family", NEW_FAMILIES)
def test_search_v5_durable_identity_and_fixed_family_choices(tmp_path, family):
    payload = seed(tmp_path, 120)
    p = protocol(payload, schema_version="search/v5", family=family, **choices(family))
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(p)
    trial = search.ask(identity)
    assert trial["spec"].signal.version == "2"
    assert trial["spec"].signal.operator == family
    assert set(trial["spec"].signal.components) == set(choices(family)["components"])
    resumed = Search(Store(tmp_path / "factory.sqlite"), tmp_path)
    assert resumed.protocol(identity).protocol_hash == identity
    resumed.enqueue_pending()
    resumed.enqueue_pending()
    assert len(store.rows("SELECT * FROM jobs")) == 1
    spec = json.loads(store.rows("SELECT spec_json FROM search_trials")[0]["spec_json"])
    assert spec["signal"]["version"] == "2"
    assert (
        store.rows(
            "SELECT proposals FROM research_coverage WHERE instrument='EURUSD' AND family=? AND timeframe='M1'",
            (family,),
        )[0]["proposals"]
        == 1
    )


def test_legacy_protocol_json_and_versions_cannot_acquire_new_families(tmp_path):
    payload = seed(tmp_path, 120)
    p = protocol(payload)
    raw = p.model_dump()
    assert "components" not in raw and "session_hours" not in raw
    assert fingerprint(raw) == p.protocol_hash
    with pytest.raises(ValidationError, match="explicit search/v5"):
        protocol(payload, family="trend")
    with pytest.raises(ValidationError, match="training only"):
        SearchProtocol.model_validate(
            {
                **raw,
                "schema_version": "search/v5",
                "window": {**raw["window"], "role": "selection_oos"},
            }
        )


def test_v4_chronological_refit_propagates_new_signal_semantics(tmp_path):
    old = protocol_fixture(tmp_path)
    assert "components" not in old.model_dump()
    raw = {
        **old.model_dump(),
        "schema_version": "scientific-validation/v4",
        "family": "confluence",
        "components": ("momentum", "trend"),
    }
    p = ValidationProtocol.model_validate(raw)
    controller = ValidationController(Store(tmp_path / "factory.sqlite"), tmp_path)
    identity = controller.register(p)
    assert controller.refit(p, 0, p.folds()[0]["train_end"]) is None
    region = controller.store.rows(
        "SELECT search_protocol_hash FROM validation_training_regions WHERE protocol_id=?",
        (identity,),
    )[0]
    child = Search(controller.store, tmp_path).protocol(region["search_protocol_hash"])
    assert child.schema_version == "search/v5" and child.family == "confluence"
    assert child.window.role == "train_only"
    assert child.window.end_ns < p.folds()[0]["oos_start"]
    assert set(child.components) == {"momentum", "trend"}
    trial = Search(controller.store, tmp_path).ask(child.protocol_hash)
    variants = list(neighbors(trial["spec"]))
    assert variants and all(v.signal.version == "2" for v in variants)
    assert not controller.store.rows("SELECT * FROM holdout_consumptions")


def test_v5_session_search_supervised_worker_feedback_runs_without_network(tmp_path, monkeypatch):
    payload = seed(tmp_path, 240)
    p = protocol(
        payload,
        schema_version="search/v5",
        family="session",
        session_hours=tuple(range(24)),
        max_trials=1,
    )
    store = Store(tmp_path / "factory.sqlite")
    search = Search(store, tmp_path)
    identity = search.register(p)
    store.pause(False, "test")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    assert cycle(store, tmp_path)
    search.feedback()
    outcomes = store.rows("SELECT * FROM search_outcomes")
    assert len(outcomes) == 1 and outcomes[0]["outcome"] == "COMPLETE"
    assert outcomes[0]["cpu_seconds"] > 0
    trial = store.rows("SELECT spec_json FROM search_trials WHERE protocol_hash=?", (identity,))[0]
    assert json.loads(trial["spec_json"])["signal"]["operator"] == "session"
    assert not search.ask(identity)  # spent budget remains spent after restart
