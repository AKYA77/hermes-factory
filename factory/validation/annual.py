"""Annual and pooled reporting over retained independent evaluations.

Reporting is descriptive. It aggregates retained evaluation windows by calendar
year and pooled, and never qualifies, ranks or promotes a strategy.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, ExperimentContract, fingerprint, serialize
from factory.data import atomic_bytes
from factory.reporting import metrics

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "annual-pooled-reporting/v1"
ATTESTATION = (
    "Report descriptive annual and pooled aggregates over retained independent "
    "evaluations only; no qualification, ranking or promotion"
)


class AnnualReportingRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


def _empty():
    return {
        "evaluations": set(),
        "windows": 0,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "ending_equity": D(0),
    }


def _finalize(entry):
    trades = entry["trades"]
    return {
        "evaluations": len(entry["evaluations"]),
        "windows": entry["windows"],
        "trades": trades,
        "wins": entry["wins"],
        "losses": entry["losses"],
        "win_rate": str(entry["wins"] / trades) if trades else None,
        "ending_equity": str(entry["ending_equity"]),
    }


class AnnualReporting:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = AnnualReportingRequest.model_validate(request)
        rows = self.store.rows(
            "SELECT evaluation_id, contract_json, result_json FROM evaluation_results "
            "ORDER BY created_at, evaluation_id"
        )
        years = defaultdict(_empty)
        pooled = _empty()
        for row in rows:
            contract = ExperimentContract.model_validate_json(row["contract_json"])
            result = json.loads(row["result_json"])
            replays = result.get("windows") or []
            for index, window in enumerate(contract.windows):
                if index >= len(replays):
                    break
                replay = replays[index].get("replay")
                if not replay:
                    continue
                year = datetime.fromtimestamp(window.start_ns / 1e9, timezone.utc).year
                stats = metrics(replay.get("trades", []))
                completed = stats["completed_trades"]
                wins = int((D(str(stats["win_rate"])) * completed).to_integral_value())
                for entry in (years[year], pooled):
                    entry["evaluations"].add(row["evaluation_id"])
                    entry["windows"] += 1
                    entry["trades"] += completed
                    entry["wins"] += wins
                    entry["losses"] += completed - wins
                    entry["ending_equity"] += D(str(replay.get("ending_equity", "0")))
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "evaluations": len(rows),
            "by_year": {str(year): _finalize(entry) for year, entry in sorted(years.items())},
            "pooled": _finalize(pooled),
            "descriptive_only": True,
            "qualification_authorized": False,
            "limitations": [
                "Descriptive aggregates over retained independent evaluations",
                "Calendar-year buckets are UTC window starts, not broker periods",
                "Pooled figures are not a paired or significance-tested comparison",
                "No protected evaluation or holdout window is reinterpreted",
                "Aggregates never qualify, rank or promote a strategy",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "annual-reporting" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable annual reporting conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "annual_reporting_reported",
                {"report_id": identity, "evaluations": len(rows)},
            )
        return body
