"""Linux parent-death binding for isolated local workers; no daemon dependency."""

import ctypes
import os
import signal


def bind_parent(expected_pid):
    if os.getppid() != expected_pid:
        raise RuntimeError("coordinator exited before worker initialization")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0):
        raise OSError(ctypes.get_errno(), "parent-death signal unavailable")
    if os.getppid() != expected_pid:
        raise RuntimeError("coordinator exited during worker initialization")
