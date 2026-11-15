"""Real loopback HTTP smoke: no browser rendering claim."""

import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error


def smoke():
    if not Path("apps/dashboard/build/index.html").exists():
        raise ValueError("build dashboard first")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "access.json").write_text(
            json.dumps(
                [{"role": "operator", "sha256": hashlib.sha256(b"synthetic-http-test").hexdigest()}]
            )
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen(
            [sys.executable, "-m", "factory.cli", "--state", tmp, "serve", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with urllib.request.urlopen(base, timeout=1) as r:
                        assert b"Hermes" in r.read()
                    break
                except (urllib.error.URLError, ConnectionError):
                    if time.monotonic() > deadline:
                        raise TimeoutError("API/dashboard startup timed out")
                    time.sleep(0.1)
            try:
                urllib.request.urlopen(base + "/api/v1/overview", timeout=3)
                raise AssertionError("anonymous API access allowed")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            req = urllib.request.Request(
                base + "/api/v1/overview", headers={"Authorization": "Bearer synthetic-http-test"}
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                overview = json.load(r)
            assert overview["status"] == "NOT_READY" and overview["paused"] is True
            return {
                "dashboard_html_served": True,
                "anonymous_api_rejected": True,
                "authenticated_overview": True,
                "scope": "real loopback HTTP; not browser E2E",
            }
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    print(json.dumps(smoke()))
