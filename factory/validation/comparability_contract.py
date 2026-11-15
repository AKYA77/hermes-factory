"""Typed comparability contract attached to retained evidence.

A comparability contract asserts which evaluation contexts may be compared with
one another. It is a guard, not a licence: a contract never qualifies, ranks or
promotes a strategy, and it refuses contexts that overlap a protected window.
"""

import time
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "comparability-contract/v1"
ATTESTATION = "Retain a typed comparability contract only; no qualification, ranking or promotion"


class ComparabilityContractRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    instrument: str
    dataset_hash: Hash
    evaluation_start_ns: int = Field(gt=0)
    evaluation_end_ns: int = Field(gt=0)
    comparable_with: tuple[Hash, ...] = Field(default=(), max_length=200)
    protected_windows: tuple[tuple[int, int], ...] = Field(default=(), max_length=50)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def ordered(self):
        if self.evaluation_end_ns <= self.evaluation_start_ns:
            raise ValueError("evaluation window must end after it starts")
        for start, end in self.protected_windows:
            if end <= start:
                raise ValueError("protected window must end after it starts")
            if not (self.evaluation_end_ns <= start or self.evaluation_start_ns >= end):
                raise ValueError("evaluation window overlaps a protected window")
        if self.evaluation_start_ns in (start for start, _ in self.protected_windows):
            raise ValueError("evaluation start collides with a protected window")
        return self


class ComparabilityContracts:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = ComparabilityContractRequest.model_validate(request)
        context = {
            "schema_version": request.schema_version,
            "instrument": request.instrument,
            "dataset_hash": request.dataset_hash,
            "window": [request.evaluation_start_ns, request.evaluation_end_ns],
        }
        identity = fingerprint(context)
        registered = self.store.rows(
            "SELECT contract_hash FROM comparability_contracts WHERE contract_hash=?", (identity,)
        )
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "context_hash": identity,
            "already_registered": bool(registered),
            "comparable_with": list(request.comparable_with),
            "protected_windows": [list(window) for window in request.protected_windows],
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "A comparability contract is a guard, not a licence",
                "It asserts only that two contexts may be compared",
                "It never qualifies, ranks or promotes a strategy",
                "Comparability is not evidence that a candidate would persist",
                "Protected windows are never entered by a registered contract",
            ],
        }
        target = self.root / "artifacts" / "comparability-contracts" / (fingerprint(body) + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable comparability contract conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            if not registered:
                db.execute(
                    "INSERT INTO comparability_contracts VALUES(?,?,?,?,?,?)",
                    (
                        identity,
                        request.instrument,
                        request.dataset_hash,
                        request.evaluation_start_ns,
                        request.evaluation_end_ns,
                        time.time(),
                    ),
                )
                for peer in request.comparable_with:
                    db.execute(
                        "INSERT INTO comparability_contract_peers VALUES(?,?)", (identity, peer)
                    )
            self.store._audit(
                db,
                request.authorized_by,
                "comparability_contract_registered",
                {"context_hash": identity, "instrument": request.instrument},
            )
        return body
