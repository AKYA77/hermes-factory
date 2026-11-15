"""Supervised immutable fixed-window evaluator. Metrics never come from the API."""

import json
from pathlib import Path
import os
import resource
import sys

from factory.contracts import ExperimentContract, fingerprint, serialize
from factory.data import atomic_bytes
from factory.validation.evaluate import evaluate


def run(payload, root):
    contract = ExperimentContract.model_validate(payload["contract"])
    result = evaluate(Path(root) / "catalog", payload)
    path = Path(root) / "artifacts" / "evaluations" / (contract.experiment_hash + ".json")
    encoded = serialize(result).encode()
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("immutable evaluation artifact conflict")
    atomic_bytes(path, encoded)
    return {"result_kind": "EVALUATION", "result": result, "artifact_hash": fingerprint(result)}


if __name__ == "__main__":
    parent = os.environ.get("FACTORY_SUPERVISED_PARENT_PID")
    if parent:
        from apps.coordinator.supervision import bind_parent

        bind_parent(int(parent))

    def measured(value):
        return {
            **value,
            "resources": {
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            },
        }

    try:
        value = run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2])
        atomic_bytes(sys.argv[3], serialize(measured(value)).encode())
    except Exception as exc:
        atomic_bytes(
            sys.argv[3],
            serialize(measured({"error": type(exc).__name__ + ": " + str(exc)})).encode(),
        )
        raise
