"""Multiple-testing safeguards for global candidate selection.

Correction is descriptive. It reports how many retained candidates would survive
a family-wise or false-discovery-rate correction. It never qualifies, ranks or
promotes a strategy, and a corrected pass is still only evidence about the
sampled historical period.
"""

from decimal import Decimal as D
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "multiple-testing/v1"
ATTESTATION = (
    "Report descriptive multiple-testing corrections for retained candidate "
    "evidence only; no qualification, ranking or promotion"
)


class MultipleTestingRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    candidate_ids: tuple[Hash, ...] = Field(min_length=1, max_length=4096)
    p_values: tuple[D, ...] = Field(min_length=1, max_length=4096)
    family_wise_alpha: D = Field(default=D("0.05"), gt=0, lt=1)
    false_discovery_rate: D = Field(default=D("0.10"), gt=0, lt=1)
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def aligned(self):
        if len(self.candidate_ids) != len(self.p_values):
            raise ValueError("candidate ids and p-values must align")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("duplicate candidate id")
        if any(not 0 <= p <= 1 for p in self.p_values):
            raise ValueError("p-values must lie in [0,1]")
        return self


def benjamini_hochberg(p_values, q):
    """Indices rejected under the Benjamini-Hochberg false discovery rate."""
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    total = len(order)
    threshold = 0
    for rank, index in enumerate(order, start=1):
        if p_values[index] <= q * D(rank) / D(total):
            threshold = rank
    return {order[rank] for rank in range(threshold)}


def bonferroni(p_values, alpha):
    """Indices rejected under a Bonferroni family-wise correction."""
    limit = alpha / D(len(p_values))
    return {index for index, value in enumerate(p_values) if value <= limit}


class MultipleTesting:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = MultipleTestingRequest.model_validate(request)
        p_values = list(request.p_values)
        uncorrected = {
            index for index, value in enumerate(p_values) if value <= request.family_wise_alpha
        }
        family = bonferroni(p_values, request.family_wise_alpha)
        discovery = benjamini_hochberg(p_values, request.false_discovery_rate)
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "candidates": len(p_values),
            "family_wise_alpha": str(request.family_wise_alpha),
            "false_discovery_rate": str(request.false_discovery_rate),
            "uncorrected_passes": len(uncorrected),
            "bonferroni_passes": len(family),
            "benjamini_hochberg_passes": len(discovery),
            "bonferroni_threshold": str(request.family_wise_alpha / D(len(p_values))),
            "candidates_considered": len(p_values),
            "selection_note": (
                "Correction counts describe how many retained candidates would "
                "survive a family-wise or false-discovery-rate correction."
            ),
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Correction is over the supplied candidate family only",
                "Correlated candidates and labels are not independent tests",
                "A corrected pass is not qualification, ranking or promotion",
                "Evidence remains about the sampled historical period",
                "Candidate ids must be distinct effective experiments",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "multiple-testing" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable multiple-testing report conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "multiple_testing_reported",
                {"report_id": identity, "candidates": len(p_values)},
            )
        return body
