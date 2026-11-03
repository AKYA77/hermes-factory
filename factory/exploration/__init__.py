"""Unmeasured template proposals only; persistent TPE lives in .persistent."""

from random import Random
from factory.contracts import Signal, StrategySpec


def propose(store, seed, budget=8):
    if not 1 <= budget <= 64:
        raise ValueError("bounded proposal budget is 1..64")
    sampler = Random(seed)
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

        spec = StrategySpec(
            instrument=row["instrument"],
            timeframe=row["timeframe"],
            signal=Signal(
                operator=row["family"],
                lookback=sampler.randint(2, 48),
                threshold=str(sampler.randint(5, 30) / 10),
            ),
            stop_ticks=sampler.randrange(20, 201, 10),
        )
        yield (
            spec,
            {
                "seed": seed,
                "proposal_index": _,
                "sampler": "seeded-template/v2; no measured objective",
                "outcome": "PROPOSED_NOT_EVALUATED",
            },
        )
