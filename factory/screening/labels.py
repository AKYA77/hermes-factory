"""Bounded fixed-horizon feature labels, NOT an execution/P&L simulator.

Midpoint close differences and an explicit two-market cost proxy can rank research
hypotheses. They do not model orders, risk sizing, stops, targets or actual fills.
A rejection suggestion is never permission to prune without native audit policy.
"""

from collections import deque
from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
import hashlib
from typing import Literal

from pydantic import Field

from factory.contracts import Contract, fingerprint, serialize
from factory.features.disk import POLICY
from factory.monetary import decimal_amount
from factory.strategies import iter_bar_signals


class CostHorizonPolicy(Contract):
    schema_version: Literal["cost-horizon-labels/v1"] = "cost-horizon-labels/v1"
    horizon_bars: int = Field(default=5, ge=1, le=1440, strict=True)
    min_labels: int = Field(default=50, ge=2, le=100000, strict=True)
    max_label_elapsed_seconds: Literal[86400] = 86400
    max_censored_fraction: D = Field(default=D(".10"), ge=0, le=1)
    dispersion_multiplier: D = Field(default=D(2), ge=0, le=10)
    rejection_score_pips: D = Field(default=D(0), le=0)
    price_basis: Literal["closed-midpoint-feature-difference"] = (
        "closed-midpoint-feature-difference"
    )
    cost_basis: Literal["hypothetical-two-market-round-trip"] = "hypothetical-two-market-round-trip"


def estimate_labels(events, spec, profile, contract, policy, *, transform_lookup=None):
    """One bounded pass, shared causal signal compiler and exact rational sums.

    Outcomes deliberately use later TRAINING features as labels. They cannot enter
    decisions or make OOS/holdout observations available to the optimizer.
    """
    policy = CostHorizonPolicy.model_validate(
        policy.model_dump() if isinstance(policy, CostHorizonPolicy) else policy
    )
    if len(contract.windows) != 1 or contract.windows[0].role != "train_only":
        raise ValueError("approximate labels require one authorized training window")
    if (
        spec.strategy_hash != contract.strategy_hash
        or fingerprint(profile) != contract.instrument_hash
        or spec.instrument != profile.instrument
    ):
        raise ValueError("approximate label contract mismatch")
    window = contract.windows[0]
    pending = deque()
    current = None
    index = -1
    prior_available = None
    signal_count = label_count = time_censored = max_pending = 0
    total, squares = Fraction(0), Fraction(0)
    signal_digest, feature_digest, label_digest = (hashlib.sha256() for _ in range(3))
    # This is a stated hypothetical two-market label convention. A real TP limit
    # exit has different costs; native audits must detect resulting disagreements.
    cost_pips = Fraction(6 if contract.scenario == "historical-pessimistic/v1" else 0)
    pip = Fraction(profile.pip_size)

    def observed():
        nonlocal current, index, prior_available, label_count, time_censored, total, squares
        for event in events:
            for tf, bar in event.items():
                if bar.end_ns > bar.available_at:
                    raise ValueError("unavailable closed feature")
                if not window.start_ns <= bar.available_at < window.end_ns:
                    raise ValueError("feature publication outside authorized training window")
            feature_digest.update(
                serialize({tf: vars(bar) for tf, bar in event.items()}).encode() + b"\n"
            )
            bar = event.get(spec.timeframe)
            if bar is not None:
                if prior_available is not None and bar.available_at <= prior_available:
                    raise ValueError("nonmonotone entry feature publication")
                prior_available = bar.available_at
                current, index = bar, index + 1
                while pending and index - pending[0]["index"] >= policy.horizon_bars:
                    origin = pending.popleft()
                    elapsed = bar.available_at - origin["available_at"]
                    if not 0 < elapsed <= policy.max_label_elapsed_seconds * 10**9:
                        time_censored += 1
                        continue
                    gross = (Fraction(bar.close) - origin["close"]) * origin["sign"] / pip
                    net = gross - cost_pips
                    total += net
                    squares += net * net
                    label_count += 1
                    label_digest.update(
                        serialize(
                            {
                                "origin_available_at": origin["available_at"],
                                "label_available_at": bar.available_at,
                                "gross_pips_numerator": gross.numerator,
                                "gross_pips_denominator": gross.denominator,
                                "net_pips_numerator": net.numerator,
                                "net_pips_denominator": net.denominator,
                            }
                        ).encode()
                        + b"\n"
                    )
            yield event

    for signal in iter_bar_signals(observed(), spec, transform_lookup=transform_lookup):
        if current is None or signal["available_at"] != current.available_at:
            raise ValueError("signal/feature availability mismatch")
        signal_digest.update(serialize(signal).encode() + b"\n")
        signal_count += 1
        pending.append(
            {
                "index": index,
                "close": Fraction(current.close),
                "available_at": current.available_at,
                "sign": 1 if signal["side"] == "BUY" else -1,
            }
        )
        max_pending = max(max_pending, len(pending))
        if len(pending) > policy.horizon_bars:
            raise ValueError("unbounded approximate label queue")
    censored = time_censored + len(pending)
    mean = total / label_count if label_count else None
    variance = squares / label_count - mean * mean if label_count else None
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        score = (
            decimal_amount(mean) + policy.dispersion_multiplier * decimal_amount(variance).sqrt()
            if label_count
            else None
        )
    enough = (
        label_count >= policy.min_labels
        and signal_count > 0
        and Fraction(censored, signal_count) <= Fraction(policy.max_censored_fraction)
    )
    return {
        "schema_version": "cost-horizon-estimate/v1",
        "policy": policy.model_dump(),
        "experiment_hash": contract.experiment_hash,
        "strategy_hash": spec.strategy_hash,
        "dataset_hash": contract.dataset_hash,
        "instrument_hash": contract.instrument_hash,
        "code_revision": contract.code_revision,
        "feature_policy": POLICY,
        "signal_count": signal_count,
        "label_count": label_count,
        "time_censored_labels": time_censored,
        "end_censored_labels": len(pending),
        "max_pending_labels": max_pending,
        "entry_bar_count": index + 1,
        "signal_sha256": signal_digest.hexdigest(),
        "feature_sha256": feature_digest.hexdigest(),
        "label_sha256": label_digest.hexdigest(),
        "hypothetical_market_cost_pips": str(cost_pips),
        "mean_net_label_pips": str(decimal_amount(mean)) if mean is not None else None,
        "population_label_variance_pips": str(decimal_amount(variance))
        if variance is not None
        else None,
        "optimistic_dispersion_score_pips": str(score) if score is not None else None,
        "rejection_suggested": bool(enough and score <= policy.rejection_score_pips),
        "evidence_status": "APPROXIMATE_TRAINING_FEATURE_LABELS_NOT_NATIVE_TRADES",
        "pruning_authorized": False,
        "limitations": [
            "feature closes are not executable entry/exit prices",
            "two-market cost proxy does not model TP limit exits or observed spread",
            "overlapping labels and dispersion score are not an IID confidence interval",
            "no order matching, sizing, stop/target, equity or scientific validation",
            "native rejection calibration and ongoing audits required before pruning",
        ],
    }


def record_native_audit(db, contract, spec, result, artifact_hash):
    """Shadow estimates never prune: every such native result supplies feedback.

    Called only within fenced official completion, after native integrity checks.
    The immutable audit preserves disagreements; no estimator can modify fills,
    objective feedback, qualification or the native artifact.
    """
    import time

    estimate = result.get("cost_horizon_labels")
    if estimate is None:
        return
    if (
        contract.evaluation_policy != "synthetic-cost-shadow-training/v1"
        or estimate.get("schema_version") != "cost-horizon-estimate/v1"
        or estimate.get("pruning_authorized") is not False
        or estimate.get("experiment_hash") != contract.experiment_hash
        or estimate.get("strategy_hash") != spec.strategy_hash
        or estimate.get("dataset_hash") != contract.dataset_hash
        or estimate.get("instrument_hash") != contract.instrument_hash
        or estimate.get("code_revision") != contract.code_revision
    ):
        raise ValueError("cost label/native contract mismatch")
    policy = CostHorizonPolicy.model_validate(estimate["policy"])
    marked = D(result["equity"]["ending_marked_equity"])
    if not marked.is_finite():
        raise ValueError("nonfinite native audit equity")
    native_positive = bool(
        result["trades"]
        and marked > contract.initial_equity
        and not result["equity"]["insolvent_at_any_observation"]
    )
    body = {
        "schema_version": "native-cost-label-audit/v1",
        "experiment_hash": contract.experiment_hash,
        "native_artifact_hash": artifact_hash,
        "synthetic": result["synthetic"],
        "dataset_hash": contract.dataset_hash,
        "instrument": spec.instrument,
        "instrument_hash": contract.instrument_hash,
        "operator": spec.signal.operator,
        "timeframe": spec.timeframe,
        "confirmations": spec.confirmations,
        "windows": contract.windows,
        "scenario": contract.scenario,
        "code_revision": contract.code_revision,
        "policy_hash": fingerprint(policy),
        "feature_label_count": estimate["label_count"],
        "signal_count": estimate["signal_count"],
        "native_closed_trades": len(result["trades"]),
        "native_marked_equity": str(marked),
        "native_positive_marked_with_closed_trades": native_positive,
        "prospective_cost_rejection": estimate["rejection_suggested"],
        "observed_false_negative": bool(estimate["rejection_suggested"] and native_positive),
        "approximate_pruning_enabled": False,
        "scope": "all native survivors of the exact-zero screen; shadow feature labels, not a validated strategy or pruning permission",
    }
    region = fingerprint(
        {
            k: body[k]
            for k in (
                "dataset_hash",
                "instrument_hash",
                "operator",
                "timeframe",
                "confirmations",
                "windows",
                "scenario",
                "code_revision",
                "policy_hash",
            )
        }
    )
    encoded = serialize(body)
    existing = db.execute(
        "SELECT body_json FROM cost_label_audits WHERE experiment_hash=?",
        (contract.experiment_hash,),
    ).fetchone()
    if existing and existing[0] != encoded:
        raise ValueError("conflicting immutable cost label audit")
    db.execute(
        "INSERT OR IGNORE INTO cost_label_audits VALUES(?,?,?,?,?)",
        (contract.experiment_hash, region, fingerprint(policy), encoded, time.time()),
    )
