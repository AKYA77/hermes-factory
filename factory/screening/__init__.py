"""Tier 0 can eliminate exact no-signal hypotheses, never promote results.

No approximate P&L or alternative matching engine is used. A deterministic
1-in-16 cohort of rejected contracts must still run through authoritative native
replay to audit the screen. Selection is independent of measured outcomes.
"""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, ExperimentContract, fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.features.disk import POLICY

SCREEN_POLICY = "exact-zero-signals-audit/16/v1"
EMPTY_SIGNAL_HASH = hashlib.sha256(b"").hexdigest()


def selected_for_audit(contract):
    return (
        int(fingerprint({"experiment": contract.experiment_hash, "policy": SCREEN_POLICY}), 16) % 16
        == 0
    )


class ScreenReceipt(Contract):
    schema_version: Literal["tier0/v1"] = "tier0/v1"
    policy: Literal["exact-zero-signals-audit/16/v1"] = SCREEN_POLICY
    feature_policy: Literal["midpoint-decimal-closed-first-later-bucket/v2"] = POLICY
    experiment_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    dataset_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    strategy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_revision: str
    signal_count: int = Field(ge=0)
    signal_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["PASS_TO_NATIVE", "PRUNE_NO_SIGNALS", "AUDIT_NO_SIGNALS"]
    synthetic: Literal[True] = True
    scientific_status: Literal["SCREEN_ONLY_NOT_VALIDATED"] = "SCREEN_ONLY_NOT_VALIDATED"

    @model_validator(mode="after")
    def coherent(self):
        if self.signal_count == 0:
            if self.signal_sha256 != EMPTY_SIGNAL_HASH or self.decision == "PASS_TO_NATIVE":
                raise ValueError("invalid no-signal screen")
        elif self.decision != "PASS_TO_NATIVE":
            raise ValueError("cannot prune a strategy with signals")
        return self


def screen(signals, contract):
    if any(w.role != "train_only" for w in contract.windows):
        raise ValueError("Tier 0 pruning is training-only")
    digest = hashlib.sha256()
    count = 0
    for signal in signals:
        digest.update(serialize(signal).encode() + b"\n")
        count += 1
    return from_summary(count, digest.hexdigest(), contract)


def from_summary(count, signal_sha256, contract):
    """Reuse an exact compiler digest without another full feature pass."""
    if any(w.role != "train_only" for w in contract.windows):
        raise ValueError("Tier 0 pruning is training-only")
    decision = (
        "PASS_TO_NATIVE"
        if count
        else "AUDIT_NO_SIGNALS"
        if selected_for_audit(contract)
        else "PRUNE_NO_SIGNALS"
    )
    return ScreenReceipt(
        experiment_hash=contract.experiment_hash,
        dataset_hash=contract.dataset_hash,
        strategy_hash=contract.strategy_hash,
        code_revision=contract.code_revision,
        signal_count=count,
        signal_sha256=signal_sha256,
        decision=decision,
    )


def persist(root, receipt):
    path = Path(root) / "artifacts" / "screens" / (receipt.experiment_hash + ".json")
    encoded = serialize(receipt).encode()
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("immutable screen receipt differs")
    atomic_bytes(path, encoded)
    return fingerprint(receipt)


def verify_pruned(root, contract, payload):
    contract = ExperimentContract.model_validate(contract)
    if any(w.role != "train_only" for w in contract.windows):
        raise ValueError("Tier 0 pruning is training-only")
    receipt = ScreenReceipt.model_validate(payload["screen"])
    expected = {
        "experiment_hash": contract.experiment_hash,
        "dataset_hash": contract.dataset_hash,
        "strategy_hash": contract.strategy_hash,
        "code_revision": contract.code_revision,
    }
    if any(getattr(receipt, k) != v for k, v in expected.items()):
        raise ValueError("screen contract mismatch")
    if receipt.decision != "PRUNE_NO_SIGNALS" or selected_for_audit(contract):
        raise ValueError("screen requires authoritative native replay")
    path = Path(root) / "artifacts" / "screens" / (contract.experiment_hash + ".json")
    digest = fingerprint(receipt)
    try:
        valid = payload["screen_artifact_hash"] == digest == sha256(path) and json.loads(
            path.read_bytes()
        ) == receipt.model_dump(mode="json")
    except (OSError, ValueError) as exc:
        raise ValueError("screen receipt integrity mismatch") from exc
    if not valid:
        raise ValueError("screen receipt integrity mismatch")
    return receipt
