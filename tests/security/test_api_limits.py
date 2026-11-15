"""C8 throttling: the API's connection and request-rate limits are enforced."""

import hashlib
import json

from fastapi.testclient import TestClient

from apps.api.main import create_app


def _client(tmp_path, tokens):
    app = create_app(tmp_path)
    (tmp_path / "access.json").write_text(
        json.dumps(
            [
                {"role": role, "sha256": hashlib.sha256(token.encode()).hexdigest()}
                for role, token in tokens.items()
            ]
        )
    )
    return TestClient(app)


def test_a_client_exceeding_the_minute_allowance_is_throttled(tmp_path):
    """120 requests per token per minute are allowed; the next one is rejected."""
    token = "throttle-test-token"
    client = _client(tmp_path, {"viewer": token})
    headers = {"Authorization": f"Bearer {token}"}
    statuses = [client.get("/api/v1/overview", headers=headers).status_code for _ in range(120)]
    assert set(statuses) == {200}, sorted(set(statuses))
    rejected = client.get("/api/v1/overview", headers=headers)
    assert rejected.status_code == 429
    assert rejected.content == b"rate limit exceeded"


def test_each_token_has_its_own_bucket(tmp_path):
    """One client being throttled must not throttle a different client."""
    victim, bystander = "victim-token", "bystander-token"
    client = _client(tmp_path, {"viewer": victim, "operator": bystander})
    for _ in range(121):
        client.get("/api/v1/overview", headers={"Authorization": f"Bearer {victim}"})
    assert (
        client.get("/api/v1/overview", headers={"Authorization": f"Bearer {victim}"}).status_code
        == 429
    )
    assert (
        client.get("/api/v1/overview", headers={"Authorization": f"Bearer {bystander}"}).status_code
        == 200
    )


def test_an_oversized_body_is_rejected_before_decoding(tmp_path):
    """Bodies over the declared ceiling are refused with 413."""
    token = "payload-test-token"
    client = _client(tmp_path, {"viewer": token})
    oversized = json.dumps({"blob": "x" * 70000})
    response = client.post(
        "/api/v1/refresh",
        data=oversized,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    # The rejection body is wrapped by the API's error handler, so match the detail.
    assert response.json()["detail"] == "payload too large"
