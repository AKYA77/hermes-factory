"""A restrictive header must permit only the trusted build's exact bootstrap."""

import base64
import hashlib
import pytest
from apps.api.security import dashboard_csp


def test_exact_bootstrap_hash_and_untrusted_script_rejection(tmp_path):
    script = 'console.log("trusted build bootstrap");'
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    html = (
        "<meta http-equiv=\"content-security-policy\" content=\"script-src 'self' 'sha256-"
        + digest
        + "'\">"
    )
    path = tmp_path / "index.html"
    path.write_text(html + "<script>" + script + "</script>")
    policy = dashboard_csp(tmp_path)
    assert "'sha256-" + digest + "'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy.split("script-src")[1]
    path.write_text(path.read_text() + '<script>console.log("injected");</script>')
    with pytest.raises(ValueError, match="bootstrap CSP mismatch"):
        dashboard_csp(tmp_path)
    assert "script-src 'self';" in dashboard_csp()
