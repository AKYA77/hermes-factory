# Development security posture

Historical and paper research only. No brokerage order execution exists.

API data and mutations require bearer credentials. Tokens are random 256-bit
values, stored locally in 0600 files, with only SHA256 digests in access.json.
Viewer tokens cannot pause/resume or submit jobs. Tokens stay in browser memory,
not localStorage. No cookie sessions, hence no cookie-based CSRF authority.
No cross-origin permission is granted. Request bodies are capped at 64KiB,
page sizes at 100, and API calls at 120/minute per credential hash. Public static
assets contain no application state. API binds to 127.0.0.1 only. Use an owner-
authorized SSH tunnel; public TLS/firewall deployment is not implemented.

No secrets are checked in or printed by credential provisioning. .local is ignored.
API does not expose shell/subprocess input or filesystem paths. Workers accept
registered declarative operators, not Python source. SQLite triggers reject
updates/deletes of experiment and audit records. Local filesystem/root access
remains trusted: these controls are not a cryptographic defense against root.

Remaining gates: dedicated service account and systemd limits; full key rotation
UX; dependency review on GitHub; protected branches; signed release provenance;
artifact authorization/export routes; full security/worker isolation tests;
secure off-host backup. Do not expose this development checkpoint publicly.
