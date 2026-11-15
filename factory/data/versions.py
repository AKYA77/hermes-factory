"""Immutable source revisions and explicit compare-and-swap current selection.

A selection is an operator choice, never scientific approval or proof of market
completeness. Frozen inputs remain reproducible; corrections get new cache keys.
"""

import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, SYMBOLS, fingerprint, serialize
from factory.experiments import Store
from factory.data import atomic_bytes
from factory.instruments.calendar import Nanoseconds


class SourceSlot(Contract):
    schema_version: Literal["source-slot/v1"] = "source-slot/v1"
    source_id: str = Field(min_length=1, max_length=128)
    instrument: str
    start_ns: Nanoseconds = Field(ge=0)
    end_ns: Nanoseconds = Field(gt=0)
    synthetic: bool = Field(strict=True)

    @model_validator(mode="after")
    def coherent(self):
        if (
            self.instrument not in SYMBOLS
            or self.start_ns >= self.end_ns
            or not self.source_id.strip()
        ):
            raise ValueError("invalid source partition scope")
        return self


def reject_quarantined(db, manifest):
    leaves = [p["dataset_hash"] for p in manifest.get("parts", ())] or [manifest["dataset_hash"]]
    for identity in (manifest["dataset_hash"], *leaves):
        if db.execute(
            """SELECT 1 FROM source_observations o JOIN source_quarantines q
            USING(observation_id) LEFT JOIN source_quarantine_resolutions r USING(quarantine_id)
            WHERE o.dataset_hash=? AND r.quarantine_id IS NULL LIMIT 1""",
            (identity,),
        ).fetchone():
            raise ValueError("QUARANTINED_SOURCE_VERSION: " + identity)


class SourceVersions:
    def __init__(self, root, catalog):
        self.root, self.catalog = Path(root), catalog
        self.store = Store(self.root / "factory.sqlite")

    def observe(self, slot, dataset_hash, actor="source-import"):
        slot = SourceSlot.model_validate(
            slot.model_dump() if isinstance(slot, SourceSlot) else slot
        )
        manifest = self.catalog.verify(dataset_hash, deep=True)
        if manifest["schema_version"] == "data/view-v1":
            raise ValueError("source revision must be one immutable leaf")
        first = next(self.catalog.read(dataset_hash))
        if (
            first.source_id != slot.source_id
            or manifest["instrument"] != slot.instrument
            or bool(manifest["provenance"].get("synthetic")) != slot.synthetic
            or manifest["first_ns"] < slot.start_ns
            or manifest["latest_verified_ns"] >= slot.end_ns
        ):
            raise ValueError("SOURCE_SLOT_BINDING_MISMATCH")
        key = fingerprint(slot)
        with self.store.transaction() as db:
            existing = db.execute(
                "SELECT observation_id FROM source_observations WHERE slot_hash=? AND dataset_hash=?",
                (key, dataset_hash),
            ).fetchone()
            if existing:
                return existing[0]
            previous = db.execute(
                "SELECT observation_id,body_json FROM source_observations WHERE slot_hash=? ORDER BY sequence DESC LIMIT 1",
                (key,),
            ).fetchone()
            prior = json.loads(previous[1]) if previous else None
            body = {
                "schema_version": "source-observation/v1",
                "slot": slot.model_dump(),
                "dataset_hash": dataset_hash,
                "manifest_sha256": fingerprint(manifest),
                "source_sha256": manifest["source_sha256"],
                "quote_stream_sha256": manifest.get("quote_stream_sha256"),
                "parent_observation_id": previous[0] if previous else None,
                "change": "INITIAL_CAPTURE"
                if prior is None
                else "SOURCE_BYTES_CHANGED"
                if prior["source_sha256"] != manifest["source_sha256"]
                else "REIMPORT_OR_PARSER_CHANGE",
                "caveat": "archive bytes changing does not by itself prove which market observations changed",
            }
            identity = fingerprint(body)
            db.execute(
                "INSERT INTO source_observations(observation_id,slot_hash,dataset_hash,body_json,created_at) VALUES(?,?,?,?,?)",
                (identity, key, dataset_hash, serialize(body), time.time()),
            )
            self.store._audit(
                db,
                actor,
                "source_version_observed",
                {"observation_id": identity, "change": body["change"]},
            )
        return identity

    def observation(self, identity, *, verify_bytes=True):
        rows = self.store.rows(
            "SELECT * FROM source_observations WHERE observation_id=?", (identity,)
        )
        if not rows:
            raise ValueError("unknown source observation")
        value = json.loads(rows[0]["body_json"])
        if fingerprint(value) != identity:
            raise ValueError("SOURCE_OBSERVATION_IDENTITY_MISMATCH")
        if (
            verify_bytes
            and fingerprint(self.catalog.verify(value["dataset_hash"])) != value["manifest_sha256"]
        ):
            raise ValueError("SOURCE_OBSERVATION_IDENTITY_MISMATCH")
        return value

    def current(self, slot):
        slot = SourceSlot.model_validate(
            slot.model_dump() if isinstance(slot, SourceSlot) else slot
        )
        rows = self.store.rows(
            "SELECT * FROM source_selections WHERE slot_hash=? ORDER BY sequence DESC LIMIT 1",
            (fingerprint(slot),),
        )
        if not rows:
            return None
        value = json.loads(rows[0]["body_json"])
        if fingerprint(value) != rows[0]["selection_id"]:
            raise ValueError("SOURCE_SELECTION_IDENTITY_MISMATCH")
        return {"selection_id": rows[0]["selection_id"], **value}

    def select(self, observation_id, *, actor, reason, expected_selection_id=None):
        if not actor.strip() or not reason.strip():
            raise ValueError("source selection requires actor and reason")
        observation = self.observation(observation_id)
        slot_hash = fingerprint(observation["slot"])
        body = {
            "schema_version": "source-selection/v1",
            "observation_id": observation_id,
            "previous_selection_id": expected_selection_id,
            "actor": actor,
            "reason": reason,
        }
        identity = fingerprint(body)
        with self.store.transaction() as db:
            if db.execute(
                "SELECT 1 FROM source_selections WHERE selection_id=?", (identity,)
            ).fetchone():
                return identity  # Idempotent receipt; never reactivates an old selection.
            manifest = self.catalog.verify(observation["dataset_hash"])
            reject_quarantined(db, manifest)
            previous = db.execute(
                "SELECT selection_id FROM source_selections WHERE slot_hash=? ORDER BY sequence DESC LIMIT 1",
                (slot_hash,),
            ).fetchone()
            if (previous[0] if previous else None) != expected_selection_id:
                raise ValueError("STALE_SOURCE_SELECTION")
            db.execute(
                "INSERT INTO source_selections(selection_id,slot_hash,observation_id,body_json,created_at) VALUES(?,?,?,?,?)",
                (identity, slot_hash, observation_id, serialize(body), time.time()),
            )
            self.store._audit(db, actor, "source_version_selected", {"selection_id": identity})
        return identity

    def quarantine(self, observation_id, actor, reason):
        if not actor.strip() or not reason.strip():
            raise ValueError("quarantine requires actor and reason")
        # Known bytes may already be corrupt. The immutable observation is enough
        # to quarantine; only byte-verified restoration can resolve an episode.
        self.observation(observation_id, verify_bytes=False)
        with self.store.transaction() as db:
            previous = db.execute(
                """SELECT q.* FROM source_quarantines q
                WHERE observation_id=? ORDER BY sequence DESC LIMIT 1""",
                (observation_id,),
            ).fetchone()
            if (
                previous
                and not db.execute(
                    "SELECT 1 FROM source_quarantine_resolutions WHERE quarantine_id=?",
                    (previous["quarantine_id"],),
                ).fetchone()
            ):
                prior = json.loads(previous["body_json"])
                if (prior["actor"], prior["reason"]) != (actor, reason):
                    raise ValueError("conflicting active source quarantine")
                return previous["quarantine_id"]
            body = {
                "schema_version": "source-quarantine/v1",
                "observation_id": observation_id,
                "previous_quarantine_id": previous["quarantine_id"] if previous else None,
                "actor": actor,
                "reason": reason,
            }
            key = fingerprint(body)
            db.execute(
                "INSERT INTO source_quarantines(quarantine_id,observation_id,body_json,created_at) VALUES(?,?,?,?)",
                (key, observation_id, serialize(body), time.time()),
            )
            self.store._audit(
                db, actor, "source_version_quarantined", {"quarantine_id": key, "reason": reason}
            )
        return key

    def resolve(self, quarantine_id, actor, reason):
        if not actor.strip() or not reason.strip():
            raise ValueError("resolution requires actor and reason")
        rows = self.store.rows(
            "SELECT observation_id FROM source_quarantines WHERE quarantine_id=?", (quarantine_id,)
        )
        if not rows:
            raise ValueError("unknown source quarantine")
        observation = self.observation(rows[0]["observation_id"])
        manifest = self.catalog.verify(observation["dataset_hash"], deep=True)
        if fingerprint(manifest) != observation["manifest_sha256"]:
            raise ValueError("restoration differs from recorded source identity")
        body = {
            "schema_version": "source-restoration/v1",
            "quarantine_id": quarantine_id,
            "manifest_sha256": fingerprint(manifest),
            "actor": actor,
            "reason": reason,
        }
        with self.store.transaction() as db:
            existing = db.execute(
                "SELECT body_json FROM source_quarantine_resolutions WHERE quarantine_id=?",
                (quarantine_id,),
            ).fetchone()
            if existing and existing[0] != serialize(body):
                raise ValueError("conflicting immutable source restoration")
            db.execute(
                "INSERT OR IGNORE INTO source_quarantine_resolutions VALUES(?,?,?)",
                (quarantine_id, serialize(body), time.time()),
            )
            self.store._audit(
                db, actor, "source_version_restored", {"quarantine_id": quarantine_id}
            )
        return fingerprint(body)

    def coverage(self):
        """Per-instrument source coverage from immutable observations and selections.

        Reports observed, selected and unresolved-quarantined counts with the
        period of each observation. A quarantine is only reflected once it is
        unresolved; a resolved quarantine stops blocking selection.
        """
        observations = self.store.rows(
            "SELECT observation_id, slot_hash, dataset_hash, body_json "
            "FROM source_observations ORDER BY sequence"
        )
        selected = {
            row["observation_id"]
            for row in self.store.rows(
                "SELECT s.observation_id FROM source_selections s JOIN "
                "(SELECT slot_hash, max(sequence) sequence FROM source_selections "
                "GROUP BY slot_hash) latest "
                "ON latest.slot_hash=s.slot_hash AND latest.sequence=s.sequence"
            )
        }
        quarantined = {
            row["observation_id"]
            for row in self.store.rows(
                "SELECT q.observation_id FROM source_quarantines q "
                "LEFT JOIN source_quarantine_resolutions r USING(quarantine_id) "
                "WHERE r.quarantine_id IS NULL"
            )
        }
        by_instrument = {}
        for row in observations:
            body = json.loads(row["body_json"])
            slot = SourceSlot.model_validate(body["slot"])
            entry = by_instrument.setdefault(
                slot.instrument,
                {"observed": 0, "selected": 0, "unresolved_quarantined": 0, "periods": []},
            )
            entry["observed"] += 1
            entry["selected"] += 1 if row["observation_id"] in selected else 0
            entry["unresolved_quarantined"] += 1 if row["observation_id"] in quarantined else 0
            entry["periods"].append(
                {
                    "observation_id": row["observation_id"],
                    "dataset_hash": row["dataset_hash"],
                    "start_ns": slot.start_ns,
                    "end_ns": slot.end_ns,
                    "selected": row["observation_id"] in selected,
                    "unresolved_quarantined": row["observation_id"] in quarantined,
                }
            )
        return {
            "schema_version": "source-coverage/v1",
            "instruments": by_instrument,
            "observed": len(observations),
            "selected": len(selected & {row["observation_id"] for row in observations}),
            "unresolved_quarantined": len(quarantined),
            "scope": "immutable source coverage; not historical approval or complete market coverage",
        }

    def snapshot(self, slots):
        if not 1 <= len(slots) <= 512:
            raise ValueError("snapshot requires 1..512 explicit source slots")
        selections, leaves = [], []
        for slot in slots:
            current = self.current(slot)
            if current is None:
                raise ValueError("SOURCE_PERIOD_NOT_SELECTED")
            observation = self.observation(current["observation_id"])
            with self.store.transaction() as db:
                reject_quarantined(db, self.catalog.verify(observation["dataset_hash"]))
            selections.append(current["selection_id"])
            leaves.append(observation["dataset_hash"])
        view = self.catalog.compose(leaves)
        if [self.current(slot)["selection_id"] for slot in slots] != selections:
            raise ValueError("SOURCE_SELECTION_CHANGED_DURING_SNAPSHOT")
        body = {
            "schema_version": "selected-source-snapshot/v1",
            "dataset_hash": view["dataset_hash"],
            "selection_ids": selections,
            "scope": "immutable selected source leaves; not historical approval or complete market coverage",
        }
        identity = fingerprint(body)
        path = self.root / "artifacts" / "source-snapshots" / (identity + ".json")
        encoded = serialize(body).encode()
        if path.exists() and path.read_bytes() != encoded:
            raise ValueError("immutable source snapshot differs")
        atomic_bytes(path, encoded)
        return {"snapshot_id": identity, **body}
