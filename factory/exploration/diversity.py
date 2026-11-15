"""Diversity-aware candidate reporting for a registered search protocol.

Diversity is descriptive. It reports how broadly a search protocol's retained
trials cover the parameter space. It never ranks, qualifies or promotes a
candidate, and it does not feed the optimizer.
"""

from collections import Counter, defaultdict
from decimal import Decimal as D
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, fingerprint, serialize
from factory.data import atomic_bytes

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "candidate-diversity/v1"
ATTESTATION = (
    "Report descriptive candidate diversity for a registered search protocol "
    "only; no qualification, ranking or promotion"
)
CONCENTRATION_LIMIT = D("0.5")
PARAMETER_FIELDS = ("lookback", "threshold_tenths", "stop_ticks")


class DiversityRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    protocol_hash: Hash
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


def _bins(values):
    """Distinct values plus coarse decile-style buckets for a numeric field."""
    distinct = sorted({v for v in values if v is not None})
    if not distinct:
        return {"distinct": 0, "buckets": []}
    low, high = distinct[0], distinct[-1]
    if high == low:
        return {"distinct": len(distinct), "buckets": [str(low)]}
    width = (high - low) / 10
    buckets = sorted({str(low + (v - low) // width) for v in distinct})
    return {"distinct": len(distinct), "buckets": buckets}


class Diversity:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = DiversityRequest.model_validate(request)
        rows = self.store.rows(
            """SELECT t.parameters_json, t.spec_json, o.outcome
               FROM search_trials t LEFT JOIN search_outcomes o USING(trial_id)
               WHERE t.protocol_hash=? ORDER BY t.trial_number""",
            (request.protocol_hash,),
        )
        if not rows:
            raise ValueError("no retained trials for this search protocol")
        outcomes = Counter(row["outcome"] or "PENDING" for row in rows)
        parameter_sets = Counter()
        operators = Counter()
        timeframes = Counter()
        strategies = set()
        values = defaultdict(list)
        for row in rows:
            parameters = json.loads(row["parameters_json"])
            spec = json.loads(row["spec_json"])
            key = json.dumps(parameters, sort_keys=True)
            parameter_sets[key] += 1
            operators[spec["signal"]["operator"]] += 1
            timeframes[spec["timeframe"]] += 1
            strategies.add(spec["signal"].get("lookback"))
            for field in PARAMETER_FIELDS:
                if field in parameters:
                    values[field].append(parameters[field])
        total = len(rows)
        largest = max(parameter_sets.values())
        share = D(largest) / D(total)
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "protocol_hash": request.protocol_hash,
            "trials": total,
            "outcomes": dict(outcomes),
            "distinct_parameter_sets": len(parameter_sets),
            "max_parameter_set_share": str(share),
            "concentrated": share > CONCENTRATION_LIMIT,
            "distinct_strategy_lookbacks": len({x for x in strategies if x is not None}),
            "operators": dict(operators),
            "timeframes": dict(timeframes),
            "parameter_coverage": {field: _bins(vals) for field, vals in values.items()},
            "descriptive_only": True,
            "limitations": [
                "Descriptive coverage of retained trials for one protocol",
                "A concentrated sample is not evidence that the region is unproductive",
                "Distinct parameter counts do not measure statistical independence",
                "No protected evaluation or holdout window is read",
                "Diversity never ranks, qualifies or promotes a candidate",
            ],
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "diversity" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable diversity report conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "candidate_diversity_reported",
                {"diversity_id": identity, "trials": total},
            )
        return body
