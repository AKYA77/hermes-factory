"""Reviewed research inputs, not a claim of broker execution or complete history.

Reviewers attest reference meaning; software proves byte/identity/scope bindings.
Only a trusted local operator may register reviews. No evidence is downloaded or
approved by an LLM, and no measured performance can be submitted here.
"""

from pathlib import Path
import time
from typing import Literal

from pydantic import Field, model_validator

from factory.contracts import Contract, InstrumentSpec, Window, fingerprint, serialize
from factory.data import atomic_bytes, sha256
from factory.data.source_quality import SourceQuality
from factory.experiments import Store
from factory.instruments.calendar import CalendarSpec, SessionCalendar, Nanoseconds

PROFILE_FIELDS = frozenset(
    {
        "tick_size",
        "pip_size",
        "price_scale",
        "base_currency",
        "quote_currency",
        "contract_multiplier",
        "volume_step",
        "min_volume",
        "max_volume",
        "margin_rate",
        "min_stop_ticks",
    }
)
CALENDAR_FIELDS = frozenset({"timezone", "weekly_sessions", "closures", "effective_period"})
POLICY_PREFIX = "historical-approved/v1:"


class Citation(Contract):
    document_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: str = Field(min_length=1, max_length=2048)
    locator: str = Field(min_length=1, max_length=1024)
    interpretation: str = Field(min_length=1, max_length=4096)
    basis: Literal["published_reference", "explicit_research_assumption"]


class ReferenceReview(Contract):
    schema_version: Literal["reference-review/v1"] = "reference-review/v1"
    profile: InstrumentSpec | None = None
    calendar: CalendarSpec | None = None
    effective_start_ns: Nanoseconds = Field(ge=0)
    effective_end_ns: Nanoseconds = Field(gt=0)
    reviewed_at_ns: Nanoseconds = Field(gt=0)
    reviewer: str = Field(min_length=1, max_length=256)
    citations: dict[str, Citation]
    attestation: Literal["I reviewed the captured references and their dated research scope"]

    @model_validator(mode="after")
    def coherent(self):
        if not self.reviewer.strip() or any(
            not value.strip()
            for citation in self.citations.values()
            for value in (citation.source, citation.locator, citation.interpretation)
        ):
            raise ValueError("reviewer and citation meaning cannot be blank")
        if (self.profile is None) == (self.calendar is None):
            raise ValueError("one profile or calendar subject required")
        if self.effective_start_ns >= self.effective_end_ns:
            raise ValueError("empty reviewed period")
        if self.profile and self.profile.synthetic:
            raise ValueError("synthetic profiles cannot become historical references")
        fields = PROFILE_FIELDS if self.profile else CALENDAR_FIELDS
        if set(self.citations) != fields:
            raise ValueError("each required specification needs an explicit reference citation")
        if self.calendar and (
            self.effective_start_ns < self.calendar.effective_start_ns
            or self.effective_end_ns > self.calendar.effective_end_ns
        ):
            raise ValueError("review exceeds calendar effective period")
        return self


class AdmissionSpec(Contract):
    schema_version: Literal["historical-admission/v1"] = "historical-admission/v1"
    quality_run_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile_review_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    calendar_review_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted_events_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    window: Window
    reviewer: str = Field(min_length=1, max_length=256)
    reviewed_at_ns: Nanoseconds = Field(gt=0)
    source_acceptance_notes: str = Field(min_length=1, max_length=16384)
    attestation: Literal["I reviewed all source QA events and accept this research input scope"]


class InputRegistry:
    def __init__(self, root, catalog):
        self.root, self.catalog = Path(root), catalog
        self.store = Store(self.root / "factory.sqlite")
        self.references = self.root / "artifacts" / "references"

    def _capture(self, data):
        import hashlib

        if not isinstance(data, bytes) or not 1 <= len(data) <= 4 * 1024**2:
            raise ValueError("reference requires 1 byte..4 MiB captured bytes")
        key = hashlib.sha256(data).hexdigest()
        path = self.references / key
        if path.is_symlink() or self.references.is_symlink():
            raise ValueError("reference symlink forbidden")
        if path.exists() and sha256(path) != key:
            raise ValueError("REFERENCE_BYTES_CHANGED")
        atomic_bytes(path, data)
        return key

    def _load(self, identity, kind):
        rows = self.store.rows("SELECT * FROM reviewed_inputs WHERE review_id=?", (identity,))
        if not rows or rows[0]["kind"] != kind:
            raise ValueError("UNKNOWN_REVIEWED_INPUT")
        if self.store.rows("SELECT * FROM input_revocations WHERE review_id=?", (identity,)):
            raise ValueError("REVOKED_REVIEWED_INPUT")
        import json

        value = json.loads(rows[0]["body_json"])
        if fingerprint(value) != identity:
            raise ValueError("REVIEW_IDENTITY_MISMATCH")
        return value

    def _put(self, kind, value, actor):
        identity = fingerprint(value)
        with self.store.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO reviewed_inputs VALUES(?,?,?,?)",
                (identity, kind, serialize(value), time.time()),
            )
            self.store._audit(db, actor, "register_reviewed_" + kind, {"review_id": identity})
        return identity

    def register_reference(self, review, documents, *, tzif=None):
        review = ReferenceReview.model_validate(
            review.model_dump() if isinstance(review, ReferenceReview) else review
        )
        required = {c.document_sha256 for c in review.citations.values()}
        if set(documents) != required or len(required) > 16:
            raise ValueError("supply exactly the captured cited documents (maximum 16)")
        for expected, data in documents.items():
            if self._capture(data) != expected:
                raise ValueError("REFERENCE_DOCUMENT_HASH_MISMATCH")
        if review.calendar:
            if self._capture(tzif) != review.calendar.tzif_sha256:
                raise ValueError("REFERENCE_TZIF_HASH_MISMATCH")
            if review.calendar.source_document_sha256 not in required:
                raise ValueError("calendar source document must be captured and cited")
            SessionCalendar(review.calendar, tzif)
        elif tzif is not None:
            raise ValueError("profile does not take a timezone artifact")
        return self._put("profile" if review.profile else "calendar", review, review.reviewer)

    def reference(self, identity, kind):
        value = ReferenceReview.model_validate(self._load(identity, kind))
        for citation in value.citations.values():
            path = self.references / citation.document_sha256
            if path.is_symlink() or self.references.is_symlink() or sha256(path) != path.name:
                raise ValueError("REFERENCE_BYTES_CHANGED")
        if value.calendar:
            path = self.references / value.calendar.tzif_sha256
            if path.is_symlink() or sha256(path) != path.name:
                raise ValueError("REFERENCE_TZIF_BYTES_CHANGED")
            SessionCalendar(value.calendar, path.read_bytes())
        return value

    def _check_admission(self, spec):
        spec = AdmissionSpec.model_validate(
            spec.model_dump() if isinstance(spec, AdmissionSpec) else spec
        )
        if not spec.reviewer.strip() or not spec.source_acceptance_notes.strip():
            raise ValueError("source review requires reviewer and substantive acceptance notes")
        profile = self.reference(spec.profile_review_id, "profile")
        calendar = self.reference(spec.calendar_review_id, "calendar")
        quality = SourceQuality(self.root, self.catalog).verify(spec.quality_run_id)
        manifest = self.catalog.verify(quality["inputs"]["dataset_hash"])
        from factory.data.versions import reject_quarantined

        with self.store.transaction() as db:
            reject_quarantined(db, manifest)
        if quality["synthetic"] or manifest["provenance"].get("synthetic"):
            raise ValueError("synthetic source cannot receive historical admission")
        if (
            not quality["complete_source_scan"]
            or quality["source_structural_status"] != "PASS"
            or quality["profile_status"] != "DECLARED_UNITS_ONLY"
            or quality["calendar_status"] != "DECLARED_RULES_ONLY"
            or quality["counts"]["calendar_rows_UNKNOWN"]
            or quality["counts"]["calendar_rows_CLOSED"]
            or quality["requested_period_status"] != "OBSERVED_WITHIN_REQUESTED_PERIOD"
        ):
            raise ValueError("SOURCE_QUALITY_NOT_ACCEPTABLE")
        if (
            quality["inputs"]["profile_hash"] != fingerprint(profile.profile)
            or quality["inputs"]["calendar_hash"] != calendar.calendar.calendar_hash
            or manifest["instrument"] != profile.profile.instrument
            or manifest["instrument"] != calendar.calendar.instrument
            or quality["events_sha256"] != spec.accepted_events_sha256
        ):
            raise ValueError("REVIEWED_SOURCE_BINDING_MISMATCH")
        policy = quality["inputs"]["policy"]
        if (policy["expected_start_ns"], policy["expected_end_ns"]) != (
            spec.window.start_ns,
            spec.window.end_ns,
        ):
            raise ValueError("ADMISSION_REQUIRES_EXACT_REVIEWED_SOURCE_PERIOD")
        for review in (profile, calendar):
            if (
                spec.window.start_ns < review.effective_start_ns
                or spec.window.end_ns > review.effective_end_ns
            ):
                raise ValueError("ADMISSION_OUTSIDE_DATED_REFERENCE")
        return spec, profile, quality

    def register_admission(self, spec):
        spec, _, _ = self._check_admission(spec)
        return self._put("admission", spec, spec.reviewer)

    def require(self, contract, profile, *, warmup_start_ns=None):
        if not contract.evaluation_policy.startswith(POLICY_PREFIX):
            raise ValueError("HISTORICAL_APPROVAL_REQUIRED")
        identity = contract.evaluation_policy[len(POLICY_PREFIX) :]
        spec, review, quality = self._check_admission(self._load(identity, "admission"))
        if contract.dataset_hash != quality["inputs"]["dataset_hash"] or fingerprint(
            profile
        ) != fingerprint(review.profile):
            raise ValueError("HISTORICAL_CONTRACT_ADMISSION_MISMATCH")
        starts = [w.start_ns for w in contract.windows]
        if warmup_start_ns is not None:
            starts.append(warmup_start_ns)
        if (
            min(starts) < spec.window.start_ns
            or max(w.end_ns for w in contract.windows) > spec.window.end_ns
        ):
            raise ValueError("HISTORICAL_WINDOW_OUTSIDE_ADMISSION")
        return {
            "admission_id": identity,
            "schema_version": spec.schema_version,
            "profile_review_id": spec.profile_review_id,
            "calendar_review_id": spec.calendar_review_id,
            "source_quality_run_id": spec.quality_run_id,
            "scope": "reviewed research assumptions and provider observations; not broker execution or independent strategy validation",
        }

    def revoke(self, identity, actor, reason):
        if not actor.strip() or not reason.strip():
            raise ValueError("revocation requires actor and reason")
        with self.store.transaction() as db:
            previous = db.execute(
                "SELECT actor,reason FROM input_revocations WHERE review_id=?", (identity,)
            ).fetchone()
            if previous:
                if tuple(previous) != (actor, reason):
                    raise ValueError("conflicting immutable input revocation")
                return
            db.execute(
                "INSERT INTO input_revocations VALUES(?,?,?,?)",
                (identity, actor, reason, time.time()),
            )
            self.store._audit(
                db, actor, "revoke_reviewed_input", {"review_id": identity, "reason": reason}
            )


def require_active_at_completion(db, contract, result, catalog_root=None):
    """Serialize revocation against official finalization in the same DB lock."""
    if db.execute("SELECT 1 FROM source_quarantines LIMIT 1").fetchone():
        from factory.data import Catalog
        from factory.data.versions import reject_quarantined

        if catalog_root is None:
            raise ValueError("catalog required for source quarantine completion check")
        reject_quarantined(db, Catalog(catalog_root).verify(contract.dataset_hash))
    if type(result.get("synthetic")) is not bool:
        raise ValueError("explicit evidence source kind required")
    if result["synthetic"]:
        if contract.evaluation_policy.startswith(POLICY_PREFIX):
            raise ValueError("historical approval cannot label synthetic output")
        return
    if not contract.evaluation_policy.startswith(POLICY_PREFIX):
        raise ValueError("HISTORICAL_APPROVAL_REQUIRED")
    identity = contract.evaluation_policy[len(POLICY_PREFIX) :]
    binding = result.get("input_admission") or {}
    if binding.get("admission_id") != identity:
        raise ValueError("HISTORICAL_RESULT_ADMISSION_MISMATCH")
    for key, kind in (
        ("admission_id", "admission"),
        ("profile_review_id", "profile"),
        ("calendar_review_id", "calendar"),
    ):
        row = db.execute(
            "SELECT body_json FROM reviewed_inputs WHERE review_id=? AND kind=?",
            (binding.get(key), kind),
        ).fetchone()
        if (
            not row
            or db.execute(
                "SELECT 1 FROM input_revocations WHERE review_id=?", (binding.get(key),)
            ).fetchone()
        ):
            raise ValueError("HISTORICAL_ADMISSION_REVOKED_OR_UNKNOWN")
        import json

        body = json.loads(row[0])
        if fingerprint(body) != binding[key]:
            raise ValueError("REVIEW_IDENTITY_MISMATCH")
        if kind == "admission":
            spec = AdmissionSpec.model_validate(body)
            if (
                spec.profile_review_id != binding.get("profile_review_id")
                or spec.calendar_review_id != binding.get("calendar_review_id")
                or spec.quality_run_id != binding.get("source_quality_run_id")
            ):
                raise ValueError("HISTORICAL_RESULT_ADMISSION_MISMATCH")
            quality = db.execute(
                "SELECT inputs_json FROM source_quality_receipts WHERE run_id=?",
                (spec.quality_run_id,),
            ).fetchone()
            if (
                not quality
                or json.loads(quality[0])["dataset_hash"] != contract.dataset_hash
                or min(w.start_ns for w in contract.windows) < spec.window.start_ns
                or max(w.end_ns for w in contract.windows) > spec.window.end_ns
            ):
                raise ValueError("HISTORICAL_CONTRACT_ADMISSION_MISMATCH")
        elif kind == "profile":
            reference = ReferenceReview.model_validate(body)
            if (
                reference.profile is None
                or fingerprint(reference.profile) != contract.instrument_hash
            ):
                raise ValueError("HISTORICAL_PROFILE_ADMISSION_MISMATCH")
