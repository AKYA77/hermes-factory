import hashlib
import json
from fastapi.testclient import TestClient
from apps.api.main import create_app
from apps.coordinator.service import cycle
from factory.operations.fixtures import seed


def test_synthetic_vertical_and_cache(tmp_path):
    payload = seed(tmp_path, 240)
    (tmp_path / "access.json").write_text(
        json.dumps([{"role": "operator", "sha256": hashlib.sha256(b"fixture").hexdigest()}])
    )
    headers = {"Authorization": "Bearer fixture"}
    app = create_app(tmp_path)
    with TestClient(app) as c:
        reply = c.post("/api/v1/research/propose", json=payload, headers=headers)
        assert reply.status_code == 202, reply.text
        assert reply.json()["status"] == "QUEUED"
        assert c.post("/api/v1/research/resume", headers=headers).status_code == 200
        assert cycle(app.state.store, tmp_path)
        job = c.get("/api/v1/jobs/" + reply.json()["job_id"], headers=headers).json()
        assert job["state"] == "COMPLETED", job
        runs = c.get("/api/v1/experiments", headers=headers).json()
        assert len(runs) == 1
        result = c.get("/api/v1/experiments/" + runs[0]["run_id"], headers=headers).json()["result"]
        assert result["engine"] == "nautilus_trader"
        assert len(result["trades"]) > 0
        assert len(result["diagnostics"]) == len(result["trades"])
        assert result["synthetic"] is True
        cached = c.post("/api/v1/research/propose", json=payload, headers=headers).json()
        assert cached["status"] == "CACHE_REUSED"
        assert len(app.state.store.rows("SELECT * FROM attempts")) == 1
        assert len(c.get("/api/v1/leaderboards/EURUSD", headers=headers).json()["candidates"]) == 1
        assert (
            c.get("/api/v1/leaderboards/EURUSD?validated_only=true", headers=headers).json()[
                "candidates"
            ]
            == []
        )
        assert c.get("/api/v1/health/ready", headers=headers).json()["operation_ready"] is False
