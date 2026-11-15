"""Restrictive security headers for the local operator API.

Headers are applied uniformly to every response. Transport security is only
asserted over an HTTPS request, because a `Strict-Transport-Security` header sent
on plaintext HTTP is ignored by browsers and would misrepresent the deployment.
"""

HEADER_POLICY = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}

HSTS = "max-age=31536000; includeSubDomains"


def apply(response, content_security_policy, *, secure=False):
    for name, value in HEADER_POLICY.items():
        response.headers[name] = value
    response.headers["Content-Security-Policy"] = content_security_policy
    if secure:
        response.headers["Strict-Transport-Security"] = HSTS
    return response
