"""Observed host/cgroup headroom; conservative admission, not a target-host proof."""

from pathlib import Path
import psutil


def memory_headroom(cgroup_root=Path("/sys/fs/cgroup")):
    host = psutil.virtual_memory()
    current_path = Path(cgroup_root) / "memory.current"
    limit_path = Path(cgroup_root) / "memory.max"
    limit, current = None, None
    if limit_path.exists():
        raw = limit_path.read_text().strip()
        if raw != "max":
            limit = int(raw)
            current = int(current_path.read_text().strip())
            if limit < 0 or current < 0:
                raise ValueError("invalid cgroup memory accounting")
    available = (
        min(host.available, max(0, limit - current)) if limit is not None else host.available
    )
    return {
        "host_total_bytes": host.total,
        "host_available_bytes": host.available,
        "cgroup_limit_bytes": limit,
        "cgroup_current_bytes": current,
        "available_bytes": available,
        "method": "min(host available, cgroup limit minus current); conservative, includes cache",
    }
