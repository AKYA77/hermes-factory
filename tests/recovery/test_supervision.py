"""Actual kernel parent-death test, independent of financial matching fixtures."""

import os
import signal
import subprocess
import sys
import time

import psutil


def test_bound_worker_dies_with_coordinator(tmp_path):
    marker = tmp_path / "bound-worker-ready"
    child_code = """
import os,signal,sys
from pathlib import Path
from apps.coordinator.supervision import bind_parent
bind_parent(int(sys.argv[1]))
Path(sys.argv[2]).write_text(str(os.getpid()))
signal.pause()
"""
    # The parent remains alive until deliberately SIGKILLed by this test.
    parent_code = """
import os,subprocess,sys,signal
subprocess.Popen([sys.executable,'-c',sys.argv[1],str(os.getpid()),sys.argv[2]])
signal.pause()
"""
    parent = subprocess.Popen(
        [sys.executable, "-c", parent_code, child_code, str(marker)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    child = None
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            assert parent.poll() is None
            time.sleep(0.02)
        assert marker.exists(), "worker never reached parent-death binding"
        child = psutil.Process(int(marker.read_text()))
        os.kill(parent.pid, signal.SIGKILL)
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            # The child can exit between the liveness check and the status read,
            # which raises NoSuchProcess. That is the expected outcome here, not a
            # failure: a process that no longer exists has died with its parent.
            try:
                if not child.is_running() or child.status() == psutil.STATUS_ZOMBIE:
                    break
            except psutil.NoSuchProcess:
                break
            time.sleep(0.02)
        try:
            assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if child is not None:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.stderr.close()
