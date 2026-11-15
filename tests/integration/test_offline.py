from apps.coordinator.service import cycle
from factory.experiments import Store
from factory.contracts import fingerprint
from factory.operations.fixtures import seed


def test_T21_no_model_or_network_dependency(tmp_path, monkeypatch):
    payload = seed(tmp_path, 120)
    store = Store(tmp_path / "factory.sqlite")
    store.enqueue("research", payload, fingerprint(payload))
    store.pause(False, "test")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    for name in ("NOUS_API_KEY", "HERMES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert cycle(store, tmp_path)
    assert store.rows("SELECT state FROM jobs")[0]["state"] == "COMPLETED"
