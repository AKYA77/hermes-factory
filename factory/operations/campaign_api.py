"""Real loopback API checks over a completed campaign database."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from factory.data import atomic_bytes


def check(root):
    root = Path(root).resolve()
    key = secrets.token_urlsafe(32)
    access = root / "access.json"
    if access.exists():
        raise ValueError("use a campaign directory without preexisting credentials")
    old = os.umask(0o077)
    try:
        atomic_bytes(
            access,
            json.dumps(
                [{"role": "operator", "sha256": hashlib.sha256(key.encode()).hexdigest()}]
            ).encode(),
        )
    finally:
        os.umask(old)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "factory.cli", "--state", str(root), "serve", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}/api/v1/"

    def request(route, auth=True):
        req = urllib.request.Request(
            base + route, headers={"Authorization": "Bearer " + key} if auth else {}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    started = time.perf_counter()
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                request("health/live")
                break
            except urllib.error.URLError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        try:
            request("overview", False)
            raise AssertionError("anonymous API allowed")
        except urllib.error.HTTPError as error:
            assert error.code == 401
        ids = []
        for offset in range(0, 1000, 100):
            ids.extend(r["run_id"] for r in request(f"experiments?limit=100&offset={offset}"))
        assert len(set(ids)) == 1000
        boards = {}
        for symbol in ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"):
            board = request("leaderboards/" + symbol)
            assert len(board["candidates"]) == 5
            assert not request("leaderboards/" + symbol + "?validated_only=true")["candidates"]
            boards[symbol] = [c["run_id"] for c in board["candidates"]]
        for run_id in ids[:6]:
            row = request("experiments/" + run_id)
            assert row["result"]["synthetic"]
            assert len(request("experiments/" + run_id + "/diagnostics")) == len(
                row["result"]["trades"]
            )
        report = {
            "status": "PASSED",
            "scope": "real authenticated loopback API over synthetic campaign",
            "unique_experiments_paginated": len(set(ids)),
            "anonymous_rejected": True,
            "top_five_boards": boards,
            "validated_boards_empty": True,
            "wall_seconds": time.perf_counter() - started,
        }
        atomic_bytes(root / "api-report.json", json.dumps(report, indent=2).encode())
        print(json.dumps(report))
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
        access.unlink()


if __name__ == "__main__":
    check(sys.argv[1])
