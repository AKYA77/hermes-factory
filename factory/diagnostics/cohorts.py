"""Aggregate retained verified training results into descriptive cohorts.

Cohort aggregation is descriptive. It never qualifies a strategy, never reads a
protected evaluation or holdout window, and never replaces authoritative native
replay. Session buckets are declared UTC hour ranges, not a verified broker
calendar.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, ExperimentContract, fingerprint, serialize
from factory.data import atomic_bytes, sha256

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
SCHEMA = "diagnostic-cohorts/v1"
ATTESTATION = (
    "Aggregate retained verified training diagnostics into descriptive cohorts only; "
    "no qualification, ranking or strategy evidence"
)
# Declared UTC hour buckets. Not a broker calendar; captured TZif session rules
# remain the authority when a reviewed calendar is supplied.
DEFAULT_SESSIONS = (
    ("ASIA", 0, 7),
    ("EUROPE", 7, 14),
    ("AMERICAS", 14, 21),
    ("OFFSHORE", 21, 24),
)


class DiagnosticCohortRequest(Contract):
    schema_version: Literal[SCHEMA] = SCHEMA
    experiment_hash: Hash
    authorized_by: str = Field(min_length=1, max_length=200)
    attestation: Literal[ATTESTATION]

    @model_validator(mode="after")
    def declared(self):
        return self


def session_label(ts_ns, sessions):
    hour = datetime.fromtimestamp(ts_ns / 1e9, timezone.utc).hour
    for name, start, end in sessions:
        if start <= hour < end:
            return name
    return "OFFSHORE"


def _bucket(stats, key, value):
    entry = stats.setdefault(
        key, {"trades": 0, "wins": 0, "losses": 0, "pnl": D(0), "losing_streak": 0}
    )
    entry["trades"] += 1
    entry["pnl"] += value
    if value > 0:
        entry["wins"] += 1
        entry["losing_streak"] = 0
    elif value < 0:
        entry["losses"] += 1
        entry["losing_streak"] += 1
    return entry


def _finalize(stats):
    out = {}
    for key, entry in stats.items():
        trades = entry["trades"]
        out[key] = {
            "trades": trades,
            "wins": entry["wins"],
            "losses": entry["losses"],
            "pnl": str(entry["pnl"]),
            "win_rate": str(entry["wins"] / trades) if trades else None,
            "losing_streak": entry["losing_streak"],
        }
    return out


def aggregate(result, sessions=DEFAULT_SESSIONS):
    """Descriptive cohort statistics from one retained native training result."""
    trades = list(result.get("trades", ()))
    closed = [t for t in trades if t.get("exit_fill")]
    session_stats = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": D(0), "losing_streak": 0}
    )
    side_stats = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": D(0), "losing_streak": 0}
    )
    tags = Counter()
    failure_groups = Counter()
    durations = []
    mfe_r = []
    mae_r = []
    equity = D(result.get("ending_equity", "0"))
    peak = equity
    drawdown = D(0)
    recovery_points = 0
    in_drawdown = False
    regime_stats = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": D(0), "losing_streak": 0}
    )
    running = D(result.get("initial_equity", "0") or 0)
    running_peak = running
    regime = "PEAK"
    max_losing_streak = 0
    losing_streak = 0
    for trade in closed:
        entry = trade["entry_fill"]
        exit_fill = trade["exit_fill"]
        side = trade["side"]
        direction = D(1) if side == "BUY" else D(-1)
        entry_price = D(entry["price"])
        realized = (D(exit_fill["price"]) - entry_price) * direction
        _bucket(regime_stats, regime, realized)
        session_label_key = session_label(entry["ts"], sessions)
        _bucket(session_stats, session_label_key, realized)
        _bucket(side_stats, side, realized)
        if realized > 0:
            losing_streak = 0
        elif realized < 0:
            losing_streak += 1
            max_losing_streak = max(max_losing_streak, losing_streak)
        was_drawdown = running < running_peak
        running += realized
        if running >= running_peak:
            running_peak = running
            regime = "RECOVERY" if was_drawdown else "PEAK"
        else:
            regime = "DRAWDOWN"
        diagnostic = trade.get("diagnostic") or {}
        trade_tags = tuple(sorted(set(diagnostic.get("tags", ()))))
        for tag in trade_tags:
            tags[tag] += 1
        failure_groups[trade_tags] += 1
        durations.append((exit_fill["ts"] - entry["ts"]) / 1e9)
        if diagnostic.get("mfe_r") is not None:
            mfe_r.append(D(diagnostic["mfe_r"]))
        if diagnostic.get("mae_r") is not None:
            mae_r.append(D(diagnostic["mae_r"]))
    equity_curve = result.get("equity", {}).get("marked_equity_curve", ()) or ()
    previous = None
    for point in equity_curve:
        value = D(str(point["marked_equity"]))
        if previous is not None and value < previous:
            in_drawdown = True
        elif previous is not None and value >= previous and in_drawdown:
            recovery_points += 1
            in_drawdown = False
        previous = value
        peak = max(peak, value)
        drawdown = max(drawdown, peak - value)
    ordered = sorted(durations)
    return {
        "schema_version": SCHEMA,
        "descriptive_only": True,
        "closed_trades": len(closed),
        "open_trades": len(trades) - len(closed),
        "unresolved_trades": sum(
            1 for t in closed if (t.get("diagnostic") or {}).get("status") != "MEASURED"
        ),
        "sessions": _finalize(session_stats),
        "sides": _finalize(side_stats),
        "equity_regimes": _finalize(regime_stats),
        "max_losing_streak": max_losing_streak,
        "stop_and_timeout_classes": dict(tags),
        "failure_pattern_groups": {
            ",".join(group) if group else "NO_TAGGED_FAILURE": count
            for group, count in failure_groups.most_common()
        },
        "excursions": {
            "mfe_r_mean": str(sum(mfe_r) / len(mfe_r)) if mfe_r else None,
            "mae_r_mean": str(sum(mae_r) / len(mae_r)) if mae_r else None,
            "measured_trades": len(mfe_r),
        },
        "hold_seconds": {
            "mean": str(sum(ordered) / len(ordered)) if ordered else None,
            "median": str(ordered[len(ordered) // 2]) if ordered else None,
            "max": str(ordered[-1]) if ordered else None,
        },
        "recovery": {
            "max_drawdown": str(drawdown),
            "recovery_events": recovery_points,
            "ending_equity": str(equity),
        },
        "cost_sensitivity": {
            "measured": False,
            "reason": "requires repeated native replay under varied cost policies, not one training result",
        },
        "limitations": [
            "Descriptive cohorts of one retained training result; not strategy qualification",
            "Session buckets are declared UTC hour ranges, not a verified broker calendar",
            "Equity regimes are derived from the realized trade sequence, not market volatility",
            "Correlated trades and overlapping positions are not independent",
            "Cost sensitivity is not measured by a single training result",
            "No protected evaluation or holdout window is read or reported",
        ],
    }


class DiagnosticCohorts:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)

    def report(self, request):
        request = DiagnosticCohortRequest.model_validate(request)
        rows = self.store.rows(
            "SELECT contract_json,result_json,artifact_hash,status FROM experiments WHERE experiment_hash=?",
            (request.experiment_hash,),
        )
        if not rows:
            raise ValueError("unknown experiment")
        row = rows[0]
        contract = ExperimentContract.model_validate_json(row["contract_json"])
        if any(w.role != "train_only" for w in contract.windows):
            raise ValueError("cohort aggregation is training-only")
        result = json.loads(row["result_json"])
        path = self.root / "artifacts" / (request.experiment_hash + ".json")
        if (
            row["status"] == "FAILED_CHECKS"
            or result.get("integrity_errors")
            or sha256(path) != row["artifact_hash"]
            or fingerprint(result) != row["artifact_hash"]
        ):
            raise ValueError("cohort aggregation artifact integrity mismatch")
        body = {
            "schema_version": request.schema_version,
            "request_hash": fingerprint(request),
            "request": request.model_dump(mode="json"),
            "experiment_hash": request.experiment_hash,
            "instrument": result.get("instrument"),
            "code_revision": contract.code_revision,
            "aggregate": aggregate(result),
        }
        identity = fingerprint(body)
        target = self.root / "artifacts" / "cohorts" / (identity + ".json")
        encoded = serialize(body).encode()
        if target.exists() and target.read_bytes() != encoded:
            raise ValueError("immutable cohort report conflict")
        atomic_bytes(target, encoded)
        with self.store.transaction() as db:
            self.store._audit(
                db,
                request.authorized_by,
                "diagnostic_cohorts_reported",
                {"cohort_report_id": identity, "experiment_hash": request.experiment_hash},
            )
        return body
