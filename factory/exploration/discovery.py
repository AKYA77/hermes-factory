"""Bounded, durable expansion of explicitly authorized training research.

Catalog presence never grants historical approval. Historical candidates come
from the reviewed admission registry; generated catalogs need an explicit
synthetic profile/time grant. The compiler and execution engine are unchanged.
"""

import fcntl
import json
from pathlib import Path
import time
from functools import cached_property
from contextlib import closing
from itertools import islice
from typing import Literal

from pydantic import Field, model_validator

from factory.contracts import (
    Contract,
    InstrumentSpec,
    Window,
    Signal,
    SignalOperator,
    UTCHour,
    TIMEFRAMES,
    OPERATORS,
    fingerprint,
    serialize,
    ExperimentContract,
)
from factory.data import Catalog
from factory.data.versions import reject_quarantined
from factory.exploration.persistent import Search, SearchProtocol
from factory.provenance import execution_revision
from factory.validation.access import check_access, evidence_kind


class Family(Contract):
    operator: SignalOperator
    components: tuple[SignalOperator, ...] = Field(default=(), max_length=3)
    session_hours: tuple[UTCHour, ...] = Field(default=(), max_length=24)

    @model_validator(mode="after")
    def valid(self):
        Signal(
            operator=self.operator,
            lookback=2,
            threshold="1",
            version="2",
            components=self.components,
            session_hours=self.session_hours,
        )
        return self


def default_families():
    return tuple(
        Family(
            operator=op,
            components=("momentum", "trend") if op == "confluence" else (),
            session_hours=tuple(range(8, 16)) if op == "session" else (),
        )
        for op in OPERATORS
    )


class DiscoveryPolicy(Contract):
    schema_version: Literal["discovery/v1"] = "discovery/v1"
    profiles: tuple[InstrumentSpec, ...] = Field(min_length=1, max_length=8)
    training_windows: tuple[Window, ...] = Field(min_length=1, max_length=16)
    families: tuple[Family, ...] = Field(
        default_factory=default_families, min_length=1, max_length=32
    )
    timeframes: tuple[str, ...] = tuple(TIMEFRAMES)
    higher_confirmations: bool = True
    code_revision: str
    seed: int = Field(ge=0, le=2**32 - 1)
    max_regions: int = Field(default=256, ge=1, le=4096)
    max_active_regions: int = Field(default=8, ge=1, le=64)
    trials_per_region: int = Field(default=16, ge=1, le=256)
    cpu_seconds_per_region: float = Field(default=120, gt=0, le=86400, allow_inf_nan=False)
    total_cpu_seconds: float = Field(default=3600, gt=0, le=86400 * 30, allow_inf_nan=False)
    authorized_by: str = Field(min_length=1, max_length=256)
    attestation: Literal[
        "I authorize training-only discovery within these bounds, never evaluation or holdout reuse"
    ]

    @model_validator(mode="after")
    def bounded(self):
        if len({p.instrument for p in self.profiles}) != len(self.profiles):
            raise ValueError("one explicit profile per instrument")
        if any(w.role != "train_only" for w in self.training_windows):
            raise ValueError("discovery requires training-only authorization")
        ordered = sorted(self.training_windows, key=lambda w: w.start_ns)
        if any(a.end_ns > b.start_ns for a, b in zip(ordered, ordered[1:])):
            raise ValueError("overlapping training grants")
        if (
            not self.timeframes
            or len(self.timeframes) > 7
            or len(set(self.timeframes)) != len(self.timeframes)
            or any(t not in TIMEFRAMES for t in self.timeframes)
        ):
            raise ValueError("invalid discovery timeframes")
        if len({fingerprint(f) for f in self.families}) != len(self.families):
            raise ValueError("duplicate discovery family")
        if not self.authorized_by.strip() or self.max_active_regions > self.max_regions:
            raise ValueError("invalid discovery authorization/budget")
        confirmations = (
            sum(1 + sum(TIMEFRAMES[x] > TIMEFRAMES[t] for x in TIMEFRAMES) for t in self.timeframes)
            if self.higher_confirmations
            else len(self.timeframes)
        )
        if len(self.training_windows) * len(self.families) * confirmations * 8 > 32768:
            raise ValueError("discovery planning exceeds 32768 bounded candidates")
        return self

    @cached_property
    def policy_id(self):
        return fingerprint(self)


def excluded_intervals(db, p, start, end):
    """Check reservations plus evaluated/frozen evaluation intervals, alias-safe.

    Old unresolvable evaluation uses conservatively exclude their whole recorded
    footprint. Known jobs retain exact windows, so prior-only warmup is not
    accidentally promoted into an OOS exclusion or a new authorization.
    """
    blocked = [
        (r[0], r[1])
        for r in db.execute(
            "SELECT start_ns,end_ns FROM protected_holdouts WHERE instrument=? AND evidence_kind=? AND start_ns<? AND end_ns>? LIMIT 4097",
            (p.instrument, evidence_kind(p), end, start),
        )
    ]
    if len(blocked) > 4096:
        raise ValueError("discovery reservation inventory exceeds budget")
    uses = list(
        db.execute(
            "SELECT * FROM research_input_uses WHERE instrument=? AND evidence_kind=? AND purpose='evaluation-with-past-only-warmup' AND start_ns<? AND end_ns>? LIMIT 4097",
            (p.instrument, evidence_kind(p), end, start),
        )
    )
    if len(uses) > 4096:
        raise ValueError("discovery influence inventory exceeds budget")
    for use in uses:
        row = db.execute(
            "SELECT payload FROM jobs WHERE kind='validation' AND idempotency_key=?",
            (use["owner_id"],),
        ).fetchone()
        result = db.execute(
            "SELECT contract_json FROM evaluation_results WHERE evaluation_id=?", (use["owner_id"],)
        ).fetchone()
        raw = json.loads(row[0])["contract"] if row else json.loads(result[0]) if result else None
        if raw is None:
            blocked.append((use["start_ns"], use["end_ns"]))
            continue
        contract = ExperimentContract.model_validate(raw)
        if contract.experiment_hash != use["owner_id"]:
            raise ValueError("evaluation influence identity mismatch")
        blocked.extend((x.start_ns, x.end_ns) for x in contract.windows if x.role != "train_only")
    # Frozen/queued stages protect their evaluation windows even before use.
    for table, column, condition in [
        ("jobs", "payload", "kind='validation'"),
        ("validation_stages", "payload_json", "1=1"),
    ]:
        jobs = db.execute(
            f"SELECT {column} FROM {table} WHERE {condition} AND json_extract({column},'$.profile.instrument')=? AND json_extract({column},'$.profile.synthetic')=? LIMIT 4097",
            (p.instrument, int(p.synthetic)),
        )
        for index, row in enumerate(jobs):
            if index >= 4096:
                raise ValueError("discovery frozen-stage inventory exceeds budget")
            value = json.loads(row[0])
            contract = ExperimentContract.model_validate(value["contract"])
            blocked.extend(
                (x.start_ns, x.end_ns) for x in contract.windows if x.role != "train_only"
            )
            if len(blocked) > 16384:
                raise ValueError("discovery exclusion inventory exceeds budget")
    return [(max(start, a), min(end, b)) for a, b in blocked if a < end and b > start]


def safe_windows(db, profile, start, end):
    windows = []
    cursor = start
    for a, b in sorted(excluded_intervals(db, profile, start, end)):
        if cursor < a:
            windows.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < end:
        windows.append((cursor, end))
    if len(windows) > 32:
        raise ValueError("discovery window fragmentation exceeds budget")
    return windows


def require_training_scope(db, protocol):
    p, w = protocol.profile, protocol.window
    check_access(db, p.instrument, evidence_kind(p), w.start_ns, w.end_ns)
    if excluded_intervals(db, p, w.start_ns, w.end_ns):
        raise ValueError("DISCOVERY_EVALUATION_WINDOW_EXCLUDED")


class Discovery:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)
        self.catalog = Catalog(self.root / "catalog")

    def register(self, policy):
        if policy.code_revision != execution_revision():
            raise ValueError("discovery source revision mismatch")
        with self.store.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO discovery_policies VALUES(?,?,?)",
                (policy.policy_id, serialize(policy), time.time()),
            )
            db.execute(
                "INSERT OR IGNORE INTO discovery_controls(policy_id,enabled) VALUES(?,1)",
                (policy.policy_id,),
            )
            self.store._audit(
                db, policy.authorized_by, "register_discovery", {"policy_id": policy.policy_id}
            )
        return policy.policy_id

    def disable(self, identity, reason="OPERATOR_DISABLED"):
        with self.store.transaction() as db:
            if not db.execute(
                "SELECT 1 FROM discovery_policies WHERE policy_id=?", (identity,)
            ).fetchone():
                raise ValueError("unknown discovery policy")
            db.execute(
                "UPDATE discovery_controls SET enabled=0,reason=? WHERE policy_id=?",
                (reason, identity),
            )
            db.execute(
                "UPDATE search_controls SET enabled=0,reason=?,updated_at=? WHERE protocol_hash IN (SELECT protocol_hash FROM discovery_regions WHERE policy_id=?)",
                (reason, time.time(), identity),
            )
            self.store._audit(
                db, "discovery", "disable_discovery", {"policy_id": identity, "reason": reason}
            )

    def block_protocol(self, identity, reason):
        rows = self.store.rows(
            "SELECT region_id FROM discovery_regions WHERE protocol_hash=?", (identity,)
        )
        if not rows:
            return False
        with self.store.transaction() as db:
            db.execute(
                "UPDATE discovery_region_controls SET state='BLOCKED',reason=? WHERE region_id=?",
                (reason[:1000], rows[0]["region_id"]),
            )
            db.execute(
                "UPDATE search_controls SET enabled=0,reason=?,updated_at=? WHERE protocol_hash=?",
                (reason[:1000], time.time(), identity),
            )
            self.store._audit(
                db,
                "discovery",
                "region_blocked",
                {"protocol_hash": identity, "reason": reason[:1000]},
            )
        return True

    def sources(self, policy, cursor):
        candidates = []
        metadata = {}
        entries = list(islice(self.catalog.root.iterdir(), 4097))
        if len(entries) > 4096:
            raise ValueError("discovery catalog inventory exceeds budget")
        synthetic = {p.instrument for p in policy.profiles if p.synthetic}
        for path in entries:
            if len(path.name) != 64 or any(c not in "0123456789abcdef" for c in path.name):
                continue
            manifest = path / "manifest.json"
            try:
                if path.is_symlink() or manifest.is_symlink():
                    raise ValueError("discovery catalog symlink forbidden")
                if manifest.stat().st_size > 1024**2:
                    raise ValueError("discovery manifest exceeds budget")
                m = json.loads(manifest.read_text())
                if (
                    m.get("dataset_hash") != path.name
                    or type(m["first_ns"]) is not int
                    or type(m["latest_verified_ns"]) is not int
                    or not isinstance(m["provenance"], dict)
                ):
                    raise ValueError("invalid discovery manifest metadata")
            except (ValueError, KeyError, TypeError, OSError) as exc:
                body = {"source": path.name, "reason": str(exc)[:1000]}
                with self.store.transaction() as db:
                    db.execute(
                        "INSERT OR IGNORE INTO discovery_source_rejections VALUES(?,?,?,?)",
                        (
                            fingerprint({"policy": policy.policy_id, **body}),
                            policy.policy_id,
                            serialize(body),
                            time.time(),
                        ),
                    )
                continue
            m = {
                key: m.get(key)
                for key in ("dataset_hash", "instrument", "first_ns", "latest_verified_ns")
            } | {"provenance": {"synthetic": m["provenance"].get("synthetic")}}
            metadata[path.name] = m
            if (
                m.get("dataset_hash") == path.name
                and m.get("provenance", {}).get("synthetic") is True
                and m.get("instrument") in synthetic
            ):
                candidates.append(("s:" + path.name, m, None))
        # A historical catalog alone cannot become a candidate. Admission scope
        # and all captured reference/revocation checks are repeated on registration.
        admissions = self.store.rows(
            """SELECT r.review_id,r.body_json,q.inputs_json FROM reviewed_inputs r
            JOIN source_quality_receipts q ON q.run_id=json_extract(r.body_json,'$.quality_run_id')
            WHERE r.kind='admission' AND NOT EXISTS(SELECT 1 FROM input_revocations v
              WHERE v.review_id IN (r.review_id,json_extract(r.body_json,'$.profile_review_id'),json_extract(r.body_json,'$.calendar_review_id')))
            ORDER BY r.review_id LIMIT 4097"""
        )
        if len(admissions) > 4096:
            raise ValueError("discovery admission inventory exceeds budget")
        for row in admissions:
            if len(candidates) > 4096:
                raise ValueError("discovery source inventory exceeds budget")
            spec = json.loads(row["body_json"])
            inputs = json.loads(row["inputs_json"])
            profile = self.store.rows(
                "SELECT body_json FROM reviewed_inputs WHERE review_id=? AND kind='profile'",
                (spec["profile_review_id"],),
            )
            if not profile:
                continue
            p = json.loads(profile[0]["body_json"])["profile"]
            if not any(
                not candidate.synthetic and fingerprint(candidate) == fingerprint(p)
                for candidate in policy.profiles
            ):
                continue
            canonical = metadata.get(inputs["dataset_hash"])
            if not canonical or canonical["provenance"]["synthetic"] is not False:
                continue
            m = {
                **canonical,
                "first_ns": max(canonical["first_ns"], spec["window"]["start_ns"]),
                "latest_verified_ns": min(
                    canonical["latest_verified_ns"], spec["window"]["end_ns"] - 1
                ),
            }
            if spec["window"]["role"] == "train_only":
                candidates.append(("h:" + row["review_id"], m, row["review_id"]))
        if len(candidates) > 4096:
            raise ValueError("discovery source inventory exceeds budget")
        candidates.sort(key=lambda x: x[0])
        after = [c for c in candidates if c[0] > cursor]
        return (after or candidates)[:8]

    def _retire(self, policy):
        rows = self.store.rows(
            """SELECT r.protocol_hash,r.region_id,r.protocol_json,count(t.trial_id) trials,
         coalesce(sum(t.generation_cpu_seconds+coalesce(o.cpu_seconds,0)),0) cpu
         FROM discovery_regions r JOIN discovery_region_controls c USING(region_id)
         LEFT JOIN search_trials t USING(protocol_hash) LEFT JOIN search_outcomes o USING(trial_id)
         WHERE r.policy_id=? AND c.state='REGISTERED' GROUP BY r.region_id""",
            (policy.policy_id,),
        )
        for r in rows:
            control = self.store.rows(
                "SELECT enabled,reason FROM search_controls WHERE protocol_hash=?",
                (r["protocol_hash"],),
            )[0]
            if not control["enabled"]:
                self.block_protocol(r["protocol_hash"], control["reason"] or "REGION_DISABLED")
                continue
            p = SearchProtocol.model_validate_json(r["protocol_json"])
            pending = self.store.rows(
                "SELECT 1 FROM search_trials t LEFT JOIN search_outcomes o USING(trial_id) WHERE t.protocol_hash=? AND o.trial_id IS NULL",
                (r["protocol_hash"],),
            )
            if not pending and (r["trials"] >= p.max_trials or r["cpu"] >= p.cpu_budget_seconds):
                with self.store.transaction() as db:
                    db.execute(
                        "UPDATE discovery_region_controls SET state='EXHAUSTED',reason='REGION_BUDGET' WHERE region_id=?",
                        (r["region_id"],),
                    )
                    db.execute(
                        "UPDATE search_controls SET enabled=0,reason='REGION_BUDGET',updated_at=? WHERE protocol_hash=?",
                        (time.time(), r["protocol_hash"]),
                    )

    def advance(self):
        if self.store.paused():
            return {"registered": 0, "reason": "PAUSED"}
        with (self.root / "discovery.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"registered": 0, "reason": "BUSY"}
            for row in self.store.rows(
                "SELECT p.*,c.source_cursor FROM discovery_policies p JOIN discovery_controls c USING(policy_id) WHERE c.enabled=1 ORDER BY p.created_at,p.policy_id"
            ):
                try:
                    policy = DiscoveryPolicy.model_validate_json(row["policy_json"])
                    if policy.policy_id != row["policy_id"]:
                        raise ValueError("discovery policy identity mismatch")
                    if policy.code_revision != execution_revision():
                        self.disable(policy.policy_id, "STALE_SOURCE")
                        continue
                    self._retire(policy)
                    used = self.store.rows(
                        """SELECT coalesce(sum(t.generation_cpu_seconds+coalesce(o.cpu_seconds,0)),0) cpu FROM discovery_regions r JOIN search_trials t USING(protocol_hash) LEFT JOIN search_outcomes o USING(trial_id) WHERE r.policy_id=?""",
                        (policy.policy_id,),
                    )[0]["cpu"]
                    if used >= policy.total_cpu_seconds:
                        self.disable(policy.policy_id, "CPU_ADMISSION_BUDGET")
                        continue
                    pending = self.store.rows(
                        "SELECT r.* FROM discovery_regions r JOIN discovery_region_controls c USING(region_id) WHERE policy_id=? AND c.state='PLANNED' ORDER BY r.created_at,r.region_id LIMIT 1",
                        (policy.policy_id,),
                    )
                    if pending:
                        return self._register(policy, pending[0])
                    active = self.store.rows(
                        "SELECT count(*) n FROM discovery_regions r JOIN discovery_region_controls c USING(region_id) WHERE policy_id=? AND c.state='REGISTERED'",
                        (policy.policy_id,),
                    )[0]["n"]
                    count = self.store.rows(
                        "SELECT count(*) n FROM discovery_regions WHERE policy_id=?",
                        (policy.policy_id,),
                    )[0]["n"]
                    if active >= policy.max_active_regions or count >= policy.max_regions:
                        continue
                    candidates = self.sources(policy, row["source_cursor"])
                    best = None
                    considered = 0
                    known = {
                        r["region_id"]
                        for r in self.store.rows(
                            "SELECT region_id FROM discovery_regions WHERE policy_id=?",
                            (policy.policy_id,),
                        )
                    }
                    counts = self.store.rows(
                        "SELECT protocol_json FROM discovery_regions WHERE policy_id=?",
                        (policy.policy_id,),
                    )
                    from collections import Counter

                    symbols = Counter()
                    datasets = Counter()
                    families = Counter()
                    frames = Counter()
                    for r in counts:
                        p = json.loads(r["protocol_json"])
                        s = p["profile"]["instrument"]
                        symbols[s] += 1
                        datasets[(s, p["dataset_hash"])] += 1
                        families[(s, p["family"])] += 1
                        frames[(s, p["family"], p["timeframe"])] += 1
                    for source_key, m, admission in candidates:
                        for profile in policy.profiles:
                            if (
                                profile.instrument != m["instrument"]
                                or profile.synthetic != m["provenance"]["synthetic"]
                            ):
                                continue
                            for grant in policy.training_windows:
                                start = max(grant.start_ns, m["first_ns"])
                                end = min(grant.end_ns, m["latest_verified_ns"] + 1)
                                if start >= end:
                                    continue
                                with closing(self.store.connect()) as read_db:
                                    allowed = safe_windows(read_db, profile, start, end)
                                for start, end in allowed:
                                    for family in policy.families:
                                        for tf in policy.timeframes:
                                            confirms = ["none"] + (
                                                [
                                                    t
                                                    for t in TIMEFRAMES
                                                    if TIMEFRAMES[t] > TIMEFRAMES[tf]
                                                ]
                                                if policy.higher_confirmations
                                                else []
                                            )
                                            for confirm in confirms:
                                                considered += 1
                                                if considered > 32768:
                                                    raise ValueError(
                                                        "discovery planning exceeds candidate budget"
                                                    )
                                                region = fingerprint(
                                                    {
                                                        "policy": policy.policy_id,
                                                        "source": source_key,
                                                        "dataset": m["dataset_hash"],
                                                        "window": [start, end],
                                                        "family": family,
                                                        "timeframe": tf,
                                                        "confirmation": confirm,
                                                    }
                                                )
                                                if region in known:
                                                    continue
                                                priority = (
                                                    symbols[profile.instrument],
                                                    datasets[
                                                        (profile.instrument, m["dataset_hash"])
                                                    ],
                                                    families[(profile.instrument, family.operator)],
                                                    frames[
                                                        (profile.instrument, family.operator, tf)
                                                    ],
                                                    region,
                                                )
                                                if best is None or priority < best[0]:
                                                    best = (
                                                        priority,
                                                        region,
                                                        dict(
                                                            schema_version="search/v5",
                                                            dataset_hash=m["dataset_hash"],
                                                            profile=profile,
                                                            window=Window(
                                                                start_ns=start,
                                                                end_ns=end,
                                                                role="train_only",
                                                            ),
                                                            family=family.operator,
                                                            components=family.components,
                                                            session_hours=family.session_hours,
                                                            timeframe=tf,
                                                            confirmation_options=(confirm,),
                                                            code_revision=policy.code_revision,
                                                            seed=(policy.seed + int(region[:8], 16))
                                                            % (2**32),
                                                            max_trials=policy.trials_per_region,
                                                            cpu_budget_seconds=policy.cpu_seconds_per_region,
                                                            admission_id=admission,
                                                            research_kind="synthetic-training/v1"
                                                            if profile.synthetic
                                                            else "historical-training/v1",
                                                        ),
                                                    )
                    with self.store.transaction() as db:
                        db.execute(
                            "UPDATE discovery_controls SET source_cursor=? WHERE policy_id=?",
                            (candidates[-1][0] if candidates else "", policy.policy_id),
                        )
                        if best:
                            _, region, raw = best
                            p = SearchProtocol(**raw)
                            db.execute(
                                "INSERT OR IGNORE INTO discovery_regions VALUES(?,?,?,?,?)",
                                (
                                    region,
                                    policy.policy_id,
                                    p.protocol_hash,
                                    serialize(p),
                                    time.time(),
                                ),
                            )
                            db.execute(
                                "INSERT OR IGNORE INTO discovery_region_controls VALUES(?,'PLANNED',NULL)",
                                (region,),
                            )
                            self.store._audit(
                                db,
                                "discovery",
                                "region_planned",
                                {
                                    "policy_id": policy.policy_id,
                                    "region_id": region,
                                    "protocol_hash": p.protocol_hash,
                                },
                            )
                    if best:
                        return self._register(
                            policy,
                            {
                                "region_id": region,
                                "protocol_json": serialize(p),
                                "protocol_hash": p.protocol_hash,
                            },
                        )
                except (ValueError, OSError) as exc:
                    self.disable(row["policy_id"], "DISCOVERY_BLOCKED: " + str(exc)[:500])
            return {"registered": 0, "reason": "NO_ELIGIBLE_EXPANSION"}

    def _register(self, policy, region):
        p = SearchProtocol.model_validate_json(region["protocol_json"])

        def guard(db):
            enabled = db.execute(
                "SELECT enabled FROM discovery_controls WHERE policy_id=?", (policy.policy_id,)
            ).fetchone()
            if not enabled or not enabled[0]:
                raise ValueError("DISCOVERY_DISABLED")
            require_training_scope(db, p)
            reject_quarantined(db, self.catalog.verify(p.dataset_hash))

        try:
            Search(self.store, self.root).register(p, registration_guard=guard)
        except (ValueError, OSError) as exc:
            with self.store.transaction() as db:
                db.execute(
                    "UPDATE discovery_region_controls SET state='BLOCKED',reason=? WHERE region_id=?",
                    (str(exc)[:1000], region["region_id"]),
                )
                self.store._audit(
                    db,
                    "discovery",
                    "registration_blocked",
                    {"region_id": region["region_id"], "reason": str(exc)[:1000]},
                )
            return {"registered": 0, "blocked": region["region_id"]}
        with self.store.transaction() as db:
            db.execute(
                "UPDATE discovery_region_controls SET state='REGISTERED',reason=NULL WHERE region_id=?",
                (region["region_id"],),
            )
            self.store._audit(
                db,
                "discovery",
                "region_registered",
                {"region_id": region["region_id"], "protocol_hash": p.protocol_hash},
            )
        return {"registered": 1, "protocol_hash": p.protocol_hash}

    def status(self, limit=50, offset=0):
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError("invalid discovery pagination")
        return {
            "current_source_revision": execution_revision(),
            "counts": self.store.rows(
                "SELECT state,count(*) count FROM discovery_region_controls GROUP BY state"
            ),
            "source_rejections": self.store.rows(
                "SELECT body_json FROM discovery_source_rejections ORDER BY created_at,rejection_id LIMIT ? OFFSET ?",
                (limit, offset),
            ),
            "policies": self.store.rows(
                "SELECT p.*,c.enabled,c.reason FROM discovery_policies p JOIN discovery_controls c USING(policy_id) ORDER BY p.created_at,p.policy_id LIMIT ? OFFSET ?",
                (limit, offset),
            ),
            "regions": self.store.rows(
                "SELECT r.*,c.state,c.reason FROM discovery_regions r JOIN discovery_region_controls c USING(region_id) ORDER BY r.created_at,r.region_id LIMIT ? OFFSET ?",
                (limit, offset),
            ),
        }
