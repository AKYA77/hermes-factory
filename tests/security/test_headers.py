"""Restrictive security header policy."""

from apps.api.headers import HEADER_POLICY, HSTS, apply


class Response:
    def __init__(self):
        self.headers = {}


def test_every_policy_header_is_applied():
    response = apply(Response(), "default-src 'self'")
    for name, value in HEADER_POLICY.items():
        assert response.headers[name] == value
    assert response.headers["Content-Security-Policy"] == "default-src 'self'"


def test_hsts_is_only_asserted_over_https():
    plaintext = apply(Response(), "default-src 'self'")
    assert "Strict-Transport-Security" not in plaintext.headers
    secure = apply(Response(), "default-src 'self'", secure=True)
    assert secure.headers["Strict-Transport-Security"] == HSTS


def test_frame_and_referrer_are_denied():
    response = apply(Response(), "default-src 'self'")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
