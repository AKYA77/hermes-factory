"""Serialized Optuna proposals restricted to training; CPU coverage ledger."""

import optuna
from factory.contracts import Signal, StrategySpec


def propose(store, seed, budget=8):
    if not 1 <= budget <= 64:
        raise ValueError("bounded proposal budget is 1..64")
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=seed))
    for _ in range(budget):
        with store.transaction() as db:
            row = db.execute(
                """SELECT c.* FROM research_coverage c
                ORDER BY (SELECT sum(i.proposals) FROM research_coverage i WHERE i.instrument=c.instrument),
                (SELECT sum(f.proposals) FROM research_coverage f WHERE f.instrument=c.instrument AND f.family=c.family),
                c.proposals,c.cpu_seconds,c.instrument,c.family,c.timeframe LIMIT 1"""
            ).fetchone()
            db.execute(
                "UPDATE research_coverage SET proposals=proposals+1 WHERE instrument=? AND family=? AND timeframe=?",
                (row["instrument"], row["family"], row["timeframe"]),
            )
        trial = study.ask()
        spec = StrategySpec(
            instrument=row["instrument"],
            timeframe=row["timeframe"],
            signal=Signal(
                operator=row["family"],
                lookback=trial.suggest_int("lookback", 2, 48),
                threshold=str(trial.suggest_int("threshold_tenths", 5, 30) / 10),
            ),
            stop_ticks=trial.suggest_int("stop_ticks", 20, 200, step=10),
        )
        study.tell(trial, state=optuna.trial.TrialState.PRUNED)
        yield (
            spec,
            {
                "seed": seed,
                "trial": trial.number,
                "sampler": "RandomSampler",
                "outcome": "PROPOSED_NOT_EVALUATED",
            },
        )
