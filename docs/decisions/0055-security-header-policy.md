# ADR0055 — Restrictive security header policy

Status: implemented software scope; full security acceptance open.

## Problem

The API applied only `X-Content-Type-Options`, `Cache-Control` and
`Content-Security-Policy`. Referrer, permissions, frame and cross-origin policies
were unset, and the header set was inline in a middleware rather than a testable
policy.

## Decision

`apps/api/headers.py` defines a single `HEADER_POLICY`:

- `X-Content-Type-Options: nosniff`
- `Cache-Control: no-store`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`
- `X-Frame-Options: DENY`

`apply(response, csp, secure=False)` sets the policy plus the CSP, and adds
`Strict-Transport-Security` **only when the request is HTTPS**. A transport
header asserted on plaintext HTTP is ignored by browsers and would misrepresent
the deployment, so it is conditional on the scheme or a forwarded-proto header.

## Safeguards

- Headers are applied uniformly to every response.
- No header is weakened by configuration.
- HSTS is never emitted over plaintext HTTP.
- `frame-ancestors 'none'` in the CSP and `X-Frame-Options: DENY` are both kept
  for defence in depth.

Evidence: docs/milestone-historical-screen-cohorts.md.
