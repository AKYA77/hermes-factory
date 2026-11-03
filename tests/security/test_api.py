import hashlib
import json
from fastapi.testclient import TestClient
from apps.api.main import create_app


def client(tmp_path):
    app = create_app(tmp_path)
    (tmp_path / "access.json").write_text(
        json.dumps(
            [
                {"role": role, "sha256": hashlib.sha256(role.encode()).hexdigest()}
                for role in ("viewer", "operator")
            ]
        )
    )
    return TestClient(app)


def test_T20_auth_pagination(tmp_path):
    c = client(tmp_path)
    assert c.get("/api/v1/overview").status_code == 401
    assert (
        c.get("/api/v1/jobs?limit=101", headers={"Authorization": "Bearer viewer"}).status_code
        == 422
    )
    assert (
        c.post("/api/v1/research/resume", headers={"Authorization": "Bearer viewer"}).status_code
        == 403
    )
    assert (
        c.get("/api/v1/overview", headers={"Authorization": "Bearer viewer"}).json()["status"]
        == "NOT_READY"
    )


def test_T28_pause_resume_audit(tmp_path):
    c = client(tmp_path)
    headers = {"Authorization": "Bearer operator"}
    assert c.post("/api/v1/research/resume", headers=headers).json() == {"paused": False}
    assert c.post("/api/v1/research/pause", headers=headers).json()["paused"]
    assert len(c.get("/api/v1/audit", headers=headers).json()) == 2


def test_T16_empty_boards(tmp_path):
    from factory.contracts import SYMBOLS

    c = client(tmp_path)
    for s in SYMBOLS:
        b = c.get("/api/v1/leaderboards/" + s, headers={"Authorization": "Bearer viewer"}).json()
        assert b["candidates"] == [] and b["max_slots"] == 5


def test_payload_cap_and_rate_limit(tmp_path):
    c = client(tmp_path)
    headers = {"Authorization": "Bearer operator"}
    assert (
        c.post("/api/v1/research/propose", content=b"x" * 65537, headers=headers).status_code == 413
    )
    statuses = [c.get("/api/v1/health/live", headers=headers).status_code for _ in range(121)]
    assert 429 in statuses


def test_data_api_does_not_publish_staged_manifests(tmp_path):
    from factory.operations.fixtures import seed

    payload = seed(tmp_path, 120)
    stage = tmp_path / "catalog" / ".pending-import"
    stage.mkdir()
    (stage / "manifest.json").write_text(json.dumps({"dataset_hash": "b" * 64, "rows": 999}))
    c = client(tmp_path)
    result = c.get("/api/v1/data/manifest", headers={"Authorization": "Bearer viewer"})
    assert result.status_code == 200
    assert [m["dataset_hash"] for m in result.json()] == [payload["contract"]["dataset_hash"]]
    assert (stage / "manifest.json").exists()


def test_training_protocol_roles_and_actions(tmp_path):
    from factory.operations.fixtures import seed
    from factory.exploration.persistent import SearchProtocol
    from factory.experiments import Store

    payload = seed(tmp_path, 120)
    p = SearchProtocol(
        dataset_hash=payload["contract"]["dataset_hash"],
        profile=payload["profile"],
        window=payload["contract"]["windows"][0],
        family="momentum",
        timeframe="M1",
        code_revision=payload["contract"]["code_revision"],
        seed=42,
        max_trials=2,
    )
    c = client(tmp_path)
    view = {"Authorization": "Bearer viewer"}
    owner = {"Authorization": "Bearer operator"}
    url = "/api/v1/research/protocols"
    assert c.post(url, json=p.model_dump(mode="json"), headers=view).status_code == 403
    response = c.post(url, json=p.model_dump(mode="json"), headers=owner)
    assert response.status_code == 200, response.text
    assert response.json()["paused"]
    identity = response.json()["protocol_hash"]
    assert len(c.get(url, headers=view).json()) == 1
    assert c.get("/api/v1/research/status", headers=view).json()["independent_validations"] == 0
    raw = p.model_dump(mode="json")
    raw["window"]["role"] = "final_holdout_unseen"
    assert c.post(url, json=raw, headers=owner).status_code == 422
    assert c.post(url + "/" + identity + "/disable", headers=view).status_code == 403
    assert c.post(url + "/" + identity + "/disable", headers=owner).status_code == 200
    store = Store(tmp_path / "factory.sqlite")
    job = store.enqueue("research", payload, "cancel-case")
    assert c.post("/api/v1/jobs/" + job + "/cancel", headers=view).status_code == 403
    assert c.post("/api/v1/jobs/" + job + "/cancel", headers=owner).status_code == 200
    assert store.rows("SELECT state FROM jobs")[0]["state"] == "CANCELLED"
