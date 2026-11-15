"""Independent software, data and target-operation gates from the owner amendment.

This evaluator does not run/waive tests. Missing gates and unverified receipts
fail closed. Bulk acquisition belongs to DATA_READY, not SOFTWARE_VERIFIED.
"""

from pathlib import Path
from typing import Literal
from pydantic import Field
from factory.contracts import Contract
from factory.data import sha256

SOFTWARE_GATES = (
    "implementation_acceptance",
    "representative_real_e2e",
    "execution_reference",
    "causality",
    "offline_coordinator",
    "diagnostics_improvement",
    "independent_validation",
    "dashboard_e2e",
    "installer_operations",
    "security_disposition",
    "reproducibility",
    "hermes_handoff",
)
DATA_GATES = (
    "full_2025_2026_coverage",
    "source_calendar_revision_reconciliation",
    "target_catalog_verified",
)
OPERATION_GATES = (
    "target_install",
    "target_8gb_stress",
    "multi_day_soak",
    "target_recovery",
    "approved_historical_workflow",
)


class Evidence(Contract):
    status: Literal["PASS", "FAIL", "BLOCKED", "NOT_TESTED"]
    receipt: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


def readiness(root, evidence):
    root = Path(root).resolve()

    def passed(name):
        check = Evidence.model_validate(evidence.get(name, {"status": "NOT_TESTED"}))
        if check.status != "PASS" or not check.receipt or not check.sha256:
            return False
        raw = root / check.receipt
        path = raw.resolve()
        if Path(check.receipt).is_absolute() or root not in path.parents or raw.is_symlink():
            return False
        return path.is_file() and sha256(path) == check.sha256

    software = all(passed(g) for g in SOFTWARE_GATES)
    data = all(passed(g) for g in DATA_GATES)
    operation = software and data and all(passed(g) for g in OPERATION_GATES)
    return {
        "schema": "readiness/v1",
        "SOFTWARE_VERIFIED": software,
        "DATA_READY": data,
        "OPERATION_READY": operation,
        "status": "OPERATION_READY"
        if operation
        else "SOFTWARE_VERIFIED"
        if software
        else "NOT_READY",
        "software_missing": [g for g in SOFTWARE_GATES if not passed(g)],
        "data_missing": [g for g in DATA_GATES if not passed(g)],
        "operation_missing": [g for g in OPERATION_GATES if not passed(g)],
    }
