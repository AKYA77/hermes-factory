"""Single authenticated API. Loopback only until authorized secure exposure."""

import hashlib
import hmac
import json
from pathlib import Path
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import psutil
from pydantic import BaseModel, ConfigDict, Field, model_validator
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, SYMBOLS, fingerprint
from factory.data import Catalog
from factory.operations.resources import memory_headroom
from factory.experiments import Store
from factory.improvement.service import ImprovementPolicy
from factory.validation.access import HoldoutSpec, Holdouts
from factory.validation.protocol import ValidationProtocol, ValidationController
from factory.ranking import leaderboard
from factory.screening.cohorts import Cohorts, CohortRequest
from factory.screening.comparability import Comparability, ComparabilityRequest
from factory.screening.historical_cohorts import HistoricalCohortRequest, HistoricalCohorts
from factory.simulation.ledger import require_execution_version, EXECUTION_VERSION
from factory.diagnostics.cohorts import DiagnosticCohortRequest, DiagnosticCohorts
from factory.improvement.sensitivity import Sensitivity, SensitivityRequest
from factory.exploration.diversity import Diversity, DiversityRequest
from factory.improvement.lineage import Lineage, LineageRequest
from factory.improvement.confirmation import Confirmation, ConfirmationRequest
from factory.exploration.persistent import Search, SearchProtocol, status as research_status


class HoldoutSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    training_run_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: StrategySpec
    contract: ExperimentContract
    profile: InstrumentSpec

    @model_validator(mode="after")
    def runtime_version(self):
        require_execution_version(self.contract)
        return self


def create_app(root, dashboard=None):
    root = Path(root)
    store = Store(root / "factory.sqlite")
    app = FastAPI(
        title="Hermes Factory",
        version="0.1.0.dev0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    from apps.api.security import dashboard_csp

    content_security_policy = dashboard_csp(dashboard)
    app.state.store = store
    from apps.api.limits import Limits

    app.add_middleware(Limits)

    @app.middleware("http")
    async def bounds(request: Request, call_next):
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 65536:
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "payload too large"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = content_security_policy
        return response

    def auth(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                401, "authentication required", headers={"WWW-Authenticate": "Bearer"}
            )
        path = root / "access.json"
        if not path.exists():
            raise HTTPException(503, "admin not provisioned")
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        for key in json.loads(path.read_text()):
            if hmac.compare_digest(digest, key["sha256"]):
                return key["role"]
        raise HTTPException(401, "invalid credentials")

    def operator(role=Depends(auth)):
        if role != "operator":
            raise HTTPException(403, "operator role required")
        return role

    read = [Depends(auth)]
    write = [Depends(operator)]

    @app.get("/api/v1/health/live", dependencies=read)
    def live():
        return {"status": "live", "scope": "historical-paper", "release": "NOT_READY"}

    @app.get("/api/v1/health/ready", dependencies=read)
    def ready():
        return {
            "platform": "available",
            "operation_ready": False,
            "research_paused": store.paused(),
            "blockers": [
                "historical source approval",
                "Gold instrument profile",
                "remaining acceptance gates",
                "VPS verification",
            ],
        }

    @app.get("/api/v1/overview", dependencies=read)
    def overview():
        return {
            "status": "NOT_READY",
            "paused": store.paused(),
            "experiments": store.rows(
                "SELECT status,count(*) AS count FROM experiments GROUP BY status"
            ),
            "jobs": store.rows("SELECT state,count(*) AS count FROM jobs GROUP BY state"),
            "resources": {
                "cpu_percent": psutil.cpu_percent(),
                "ram_used_bytes": psutil.virtual_memory().used,
                "ram_available_bytes": memory_headroom()["available_bytes"],
                "memory_headroom": memory_headroom(),
                "disk_free_bytes": psutil.disk_usage(root).free,
            },
            "hermes": {"configured": False, "required_for_research": False},
        }

    @app.get("/api/v1/research/status", dependencies=read)
    def search_status():
        return research_status(store)

    @app.get("/api/v1/research/screen-cohort-inputs", dependencies=read)
    def screen_cohort_inputs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        from factory.provenance import execution_revision

        revision = execution_revision()
        calibration = store.rows(
            """SELECT experiment_hash,
            json_extract(body_json,'$.instrument') instrument,
            json_extract(body_json,'$.operator') operator,
            json_extract(body_json,'$.timeframe') timeframe,
            json_extract(body_json,'$.native_closed_trades') native_closed_trades,
            json_extract(body_json,'$.observed_false_negative') observed_false_negative
            FROM cost_label_audits WHERE json_extract(body_json,'$.code_revision')=?
            ORDER BY created_at,experiment_hash LIMIT ? OFFSET ?""",
            (revision, limit, offset),
        )
        prospective = store.rows(
            """SELECT j.job_id,
            json_extract(j.payload,'$.strategy.instrument') instrument,
            json_extract(j.payload,'$.strategy.signal.operator') operator,
            json_extract(j.payload,'$.strategy.timeframe') timeframe
            FROM jobs j WHERE j.kind='research' AND j.state='QUEUED' AND j.attempts=0
            AND json_extract(j.payload,'$.contract.evaluation_policy')='synthetic-cost-shadow-training/v1'
            AND json_extract(j.payload,'$.contract.code_revision')=?
            AND NOT EXISTS(SELECT 1 FROM screen_cohort_members m WHERE m.job_id=j.job_id AND m.role='prospective')
            ORDER BY j.created_at,j.job_id LIMIT ? OFFSET ?""",
            (revision, limit, offset),
        )
        return {
            "calibration": calibration,
            "prospective": prospective,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/v1/research/historical-screen-cohort-inputs", dependencies=read)
    def historical_screen_cohort_inputs(
        limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
    ):
        from factory.data.admission import admission_identity
        from factory.provenance import execution_revision

        revision = execution_revision()
        calibration = []
        for row in store.rows(
            """SELECT e.experiment_hash, e.contract_json,
                       json_extract(a.payload,'$.artifact_hash') AS diagnostic_artifact_hash,
                       json_extract(a.payload,'$.estimate_hash') AS estimate_hash
                FROM audit_events a
                JOIN experiments e ON e.artifact_hash = json_extract(a.payload,'$.native_artifact_hash')
                WHERE a.action='historical_shadow_completed'
                ORDER BY a.created_at, e.experiment_hash LIMIT 500"""
        ):
            contract = json.loads(row["contract_json"])
            if contract.get("code_revision") != revision:
                continue
            try:
                admission = admission_identity(contract.get("evaluation_policy", ""))
            except ValueError:
                continue
            window = contract["windows"][0]
            calibration.append(
                {
                    "experiment_hash": row["experiment_hash"],
                    "admission_id": admission,
                    "dataset_hash": contract["dataset_hash"],
                    "profile_hash": contract["instrument_hash"],
                    "code_revision": contract["code_revision"],
                    "training_start_ns": window["start_ns"],
                    "training_end_ns": window["end_ns"],
                    "evaluation_policy": contract["evaluation_policy"],
                    "diagnostic_artifact_hash": row["diagnostic_artifact_hash"],
                    "estimate_hash": row["estimate_hash"],
                }
            )
        prospective = store.rows(
            """SELECT j.job_id,
                       json_extract(j.payload,'$.contract.evaluation_policy') AS evaluation_policy,
                       json_extract(j.payload,'$.contract.dataset_hash') AS dataset_hash,
                       json_extract(j.payload,'$.contract.instrument_hash') AS profile_hash,
                       json_extract(j.payload,'$.contract.code_revision') AS code_revision,
                       json_extract(j.payload,'$.contract.windows[0].start_ns') AS start_ns,
                       json_extract(j.payload,'$.contract.windows[0].end_ns') AS end_ns
                FROM jobs j WHERE j.kind='research' AND j.state='QUEUED' AND j.attempts=0
                AND json_extract(j.payload,'$.contract.evaluation_policy') LIKE 'historical-approved/%'
                AND json_extract(j.payload,'$.contract.code_revision')=?
                AND NOT EXISTS(SELECT 1 FROM screen_cohort_members m
                               WHERE m.job_id=j.job_id AND m.role='prospective')
                ORDER BY j.created_at, j.job_id LIMIT ? OFFSET ?""",
            (revision, limit, offset),
        )
        for row in prospective:
            row["admission_id"] = admission_identity(row["evaluation_policy"])
        return {
            "calibration": calibration[offset : offset + limit],
            "prospective": prospective,
            "limit": limit,
            "offset": offset,
            "scope": (
                "Reviewed-admission historical training inputs only; not broker execution, "
                "independent strategy validation or DATA_READY evidence"
            ),
        }

    @app.post("/api/v1/research/screen-cohorts", dependencies=write)
    def freeze_screen_cohort(payload: CohortRequest):
        return {"cohort_id": Cohorts(store, root).freeze(payload)}

    @app.post("/api/v1/research/historical-screen-cohorts", dependencies=write)
    def freeze_historical_screen_cohort(payload: HistoricalCohortRequest):
        return {"cohort_id": HistoricalCohorts(store, root).freeze(payload)}

    @app.post("/api/v1/research/screen-comparability", dependencies=read)
    def screen_comparability(payload: ComparabilityRequest):
        return Comparability(store, root).compare(payload)

    @app.post("/api/v1/research/diagnostic-cohorts", dependencies=read)
    def diagnostic_cohorts(payload: DiagnosticCohortRequest):
        return DiagnosticCohorts(store, root).report(payload)

    @app.post("/api/v1/research/improvement-sensitivity", dependencies=read)
    def improvement_sensitivity(payload: SensitivityRequest):
        return Sensitivity(store, root).report(payload)

    @app.post("/api/v1/research/candidate-diversity", dependencies=read)
    def candidate_diversity(payload: DiversityRequest):
        return Diversity(store, root).report(payload)

    @app.post("/api/v1/research/improvement-lineage", dependencies=read)
    def improvement_lineage(payload: LineageRequest):
        return Lineage(store, root).report(payload)

    @app.post("/api/v1/research/improvement-confirmation", dependencies=read)
    def improvement_confirmation(payload: ConfirmationRequest):
        return Confirmation(store, root).confirm(payload)

    @app.get("/api/v1/research/screen-cohorts", dependencies=read)
    def screen_cohorts(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return {
            "cohorts": store.rows(
                "SELECT cohort_id,created_at FROM screen_cohorts ORDER BY created_at,cohort_id LIMIT ? OFFSET ?",
                (limit, offset),
            ),
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/v1/research/screen-cohorts/{identity}", dependencies=read)
    def screen_cohort_report(identity: str):
        return Cohorts(store, root).report(identity)

    from factory.exploration.discovery import Discovery, DiscoveryPolicy

    @app.get("/api/v1/research/discovery", dependencies=read)
    def discovery_status(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        return Discovery(store, root).status(limit, offset)

    @app.post("/api/v1/research/discovery", dependencies=write)
    def register_discovery(policy: DiscoveryPolicy):
        try:
            identity = Discovery(store, root).register(policy)
            return {"policy_id": identity, "paused": store.paused()}
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/v1/research/discovery/{identity}/disable", dependencies=write)
    def disable_discovery(identity: str):
        try:
            Discovery(store, root).disable(identity)
            return {"policy_id": identity, "enabled": False}
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/v1/improvement/status", dependencies=read)
    def improvement_status():
        from factory.improvement.service import Improvement

        return Improvement(store, root).status()

    @app.post("/api/v1/improvement/policies", dependencies=write)
    def register_improvement(policy: ImprovementPolicy):
        from factory.improvement.service import Improvement

        try:
            identity = Improvement(store, root).register(policy)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"policy_hash": identity, "paused": store.paused()}

    @app.post("/api/v1/improvement/policies/{identity}/disable", dependencies=write)
    def disable_improvement(identity: str):
        from factory.improvement.service import Improvement

        try:
            Improvement(store, root).disable(identity)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"policy_hash": identity, "enabled": False}

    @app.get("/api/v1/improvement/plans", dependencies=read)
    def improvement_plans(
        limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
    ):
        return store.rows(
            "SELECT * FROM improvement_plans ORDER BY created_at,plan_hash LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.get("/api/v1/improvement/children", dependencies=read)
    def improvement_children(
        limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
    ):
        return store.rows(
            "SELECT e.*,o.status,o.evidence_json,o.cpu_seconds FROM improvement_edges e LEFT JOIN improvement_outcomes o USING(edge_id) ORDER BY e.created_at,e.edge_id LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.post("/api/v1/validation/protocols", dependencies=write)
    def register_validation(protocol: ValidationProtocol):
        try:
            identity = ValidationController(store, root).register(protocol)
            return {"protocol_id": identity, "paused": store.paused()}
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/validation/protocols", dependencies=read)
    def validation_protocols(
        limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
    ):
        return store.rows(
            "SELECT p.*,c.enabled,r.artifact_hash,json_extract(r.report_json,'$.status') status FROM validation_protocols p JOIN validation_controls c USING(protocol_id) LEFT JOIN validation_protocol_reports r USING(protocol_id) ORDER BY p.created_at DESC,p.protocol_id LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.get("/api/v1/validation/protocols/{identity}", dependencies=read)
    def validation_protocol_report(identity: str):
        try:
            controller = ValidationController(store, root)
            protocol = controller.protocol(identity)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        reports = store.rows(
            "SELECT report_json,artifact_hash FROM validation_protocol_reports WHERE protocol_id=?",
            (identity,),
        )
        stages = store.rows(
            "SELECT s.stage_id,s.stage_name,s.training_run_id,j.state,j.error FROM validation_stages s LEFT JOIN jobs j ON json_extract(j.payload,'$.validation_stage_id')=s.stage_id WHERE s.protocol_id=? ORDER BY s.created_at,s.stage_id",
            (identity,),
        )
        regions = store.rows(
            "SELECT * FROM validation_training_regions WHERE protocol_id=? ORDER BY fold_index",
            (identity,),
        )
        return {
            "protocol": protocol.model_dump(mode="json"),
            "folds": protocol.folds(),
            "stages": stages,
            "training_regions": regions,
            "report": json.loads(reports[0]["report_json"]) if reports else None,
            "artifact_hash": reports[0]["artifact_hash"] if reports else None,
        }

    @app.post("/api/v1/validation/protocols/{identity}/disable", dependencies=write)
    def disable_validation(identity: str):
        with store.transaction() as db:
            if not db.execute(
                "UPDATE validation_controls SET enabled=0 WHERE protocol_id=?", (identity,)
            ).rowcount:
                raise HTTPException(404, "unknown validation protocol")
            store._audit(db, "operator", "validation_disabled", {"protocol_id": identity})
        return {"protocol_id": identity, "enabled": False}

    @app.get("/api/v1/validation/holdouts", dependencies=read)
    def holdouts(
        limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
    ):
        return Holdouts(root).status(limit, offset)

    @app.post("/api/v1/validation/holdouts", dependencies=write)
    def reserve_holdout(spec: HoldoutSpec):
        try:
            return {"holdout_id": Holdouts(root).register(spec)}
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/v1/validation/holdouts/{identity}/freeze", dependencies=write)
    def freeze_holdout(identity: str, selection: HoldoutSelection):
        try:
            payload = Holdouts(root).freeze(identity, selection.training_run_id)
            return {
                "holdout_id": identity,
                "contract": payload["contract"],
                "status": "CANDIDATE_FROZEN",
            }
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/v1/validation/holdouts/{identity}/evaluate", dependencies=write)
    def evaluate_holdout(identity: str):
        try:
            return Holdouts(root).enqueue(identity)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/validation/evaluations", dependencies=read)
    def evaluation_list(
        limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0)
    ):
        return store.rows(
            "SELECT evaluation_id,contract_json,artifact_hash,holdout_id,created_at FROM evaluation_results ORDER BY created_at DESC,evaluation_id LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.get("/api/v1/validation/evaluations/{identity}", dependencies=read)
    def evaluation_detail(identity: str):
        rows = store.rows("SELECT * FROM evaluation_results WHERE evaluation_id=?", (identity,))
        if not rows:
            raise HTTPException(404, "evaluation not found")
        row = rows[0]
        row["contract"] = json.loads(row.pop("contract_json"))
        row["result"] = json.loads(row.pop("result_json"))
        return row

    @app.get("/api/v1/research/protocols", dependencies=read)
    def search_protocols(
        limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
    ):
        return store.rows(
            "SELECT p.*,c.enabled,c.reason FROM search_protocols p JOIN search_controls c USING(protocol_hash) ORDER BY p.created_at,p.protocol_hash LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.post("/api/v1/research/protocols", dependencies=write)
    def register_search(protocol: SearchProtocol):
        try:
            identity = Search(store, root).register(protocol)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"protocol_hash": identity, "paused": store.paused()}

    @app.post("/api/v1/research/protocols/{identity}/disable", dependencies=write)
    def disable_search(identity: str):
        try:
            Search(store, root).set_enabled(identity, False)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"protocol_hash": identity, "enabled": False}

    @app.get("/api/v1/research/trials", dependencies=read)
    def search_trials(
        limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
    ):
        return store.rows(
            "SELECT t.*,o.outcome,o.objective,o.run_id,o.cpu_seconds,o.reason FROM search_trials t LEFT JOIN search_outcomes o USING(trial_id) ORDER BY t.created_at,t.trial_id LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.post("/api/v1/jobs/{job_id}/cancel", dependencies=write)
    def cancel_job(job_id: str):
        try:
            store.cancel(job_id, "operator")
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"job_id": job_id, "state": "CANCELLED"}

    @app.get("/api/v1/instruments", dependencies=read)
    def instruments():
        return [
            {"instrument": s, "status": "DATA_UNAVAILABLE", "profile": "UNKNOWN_SPEC"}
            for s in SYMBOLS
        ]

    @app.get("/api/v1/leaderboards/{symbol}", dependencies=read)
    def board(
        symbol: str,
        validated_only: bool = False,
        execution_version: Literal[
            "adverse-fill/v1", "adverse-fill/v2", "adverse-fill/v3", "adverse-fill/v4"
        ]
        | None = None,
    ):
        if symbol not in SYMBOLS:
            raise HTTPException(404, "unknown instrument")
        return leaderboard(store, symbol, validated_only, execution_version or EXECUTION_VERSION)

    @app.get("/api/v1/jobs", dependencies=read)
    def jobs(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.rows(
            "SELECT job_id,kind,state,attempts,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.get("/api/v1/jobs/{job_id}", dependencies=read)
    def job(job_id: str):
        rows = store.rows("SELECT * FROM jobs WHERE job_id=?", (job_id,))
        if not rows:
            raise HTTPException(404, "job not found")
        return rows[0]

    @app.post("/api/v1/research/pause", dependencies=write)
    def pause():
        store.pause(True, "api-operator")
        return {"paused": True, "running_job_policy": "finish current job"}

    @app.post("/api/v1/research/resume", dependencies=write)
    def resume():
        store.pause(False, "api-operator")
        return {"paused": False}

    @app.post("/api/v1/research/propose", dependencies=write, status_code=202)
    def proposal(p: Proposal):
        if (
            p.contract.strategy_hash != p.strategy.strategy_hash
            or p.contract.instrument_hash != fingerprint(p.profile)
        ):
            raise HTTPException(422, "contract hashes mismatch")
        if p.strategy.instrument != p.profile.instrument:
            raise HTTPException(422, "instrument mismatch")
        try:
            Catalog(root / "catalog").verify(p.contract.dataset_hash)
        except (ValueError, OSError):
            raise HTTPException(422, "verified dataset required")
        if any(w.role != "train_only" for w in p.contract.windows):
            raise HTTPException(422, "OOS worker not implemented; training proposals only")
        store.register_strategy(p.strategy)
        run = store.rows(
            "SELECT run_id FROM experiments WHERE experiment_hash=?", (p.contract.experiment_hash,)
        )
        if run:
            return {"status": "CACHE_REUSED", "run_id": run[0]["run_id"]}
        try:
            job_id = store.enqueue(
                "research",
                p.model_dump(mode="json"),
                p.contract.experiment_hash,
                actor="api-operator",
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "QUEUED", "job_id": job_id}

    @app.get("/api/v1/experiments", dependencies=read)
    def experiments(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.rows(
            "SELECT run_id,strategy_id,instrument,status,created_at FROM experiments ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def get_run(run_id):
        rows = store.rows("SELECT * FROM experiments WHERE run_id=?", (run_id,))
        if not rows:
            raise HTTPException(404, "experiment not found")
        return rows[0]

    @app.get("/api/v1/experiments/{run_id}", dependencies=read)
    def experiment(run_id: str):
        r = get_run(run_id)
        r["contract"] = json.loads(r.pop("contract_json"))
        r["result"] = json.loads(r.pop("result_json"))
        return r

    @app.get("/api/v1/experiments/{run_id}/trades", dependencies=read)
    def trades(run_id: str, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return json.loads(get_run(run_id)["result_json"])["trades"][offset : offset + limit]

    @app.get("/api/v1/experiments/{run_id}/diagnostics", dependencies=read)
    def diagnostics(run_id: str):
        return json.loads(get_run(run_id)["result_json"])["diagnostics"]

    @app.get("/api/v1/strategies/{strategy_id}", dependencies=read)
    def strategy(strategy_id: str):
        rows = store.rows("SELECT * FROM strategy_specs WHERE strategy_id=?", (strategy_id,))
        if not rows:
            raise HTTPException(404, "strategy not found")
        return rows[0]

    @app.get("/api/v1/strategies/{strategy_id}/lineage", dependencies=read)
    def lineage(strategy_id: str):
        return store.rows(
            "SELECT strategy_id,parent_id,hypothesis,changed_fields FROM strategy_specs WHERE strategy_id=? OR parent_id=?",
            (strategy_id, strategy_id),
        )

    @app.get("/api/v1/coverage", dependencies=read)
    def coverage():
        return store.rows("SELECT * FROM research_coverage ORDER BY instrument,family,timeframe")

    @app.get("/api/v1/data/manifest", dependencies=read)
    def manifests():
        manifests = []
        for path in sorted((root / "catalog").glob("*/manifest.json")):
            name = path.parent.name
            # A verified staging manifest is not committed until directory rename.
            if (
                len(name) != 64
                or any(c not in "0123456789abcdef" for c in name)
                or path.parent.is_symlink()
            ):
                continue
            value = json.loads(path.read_text())
            if value.get("dataset_hash") != name:
                raise HTTPException(409, "manifest namespace mismatch")
            manifests.append(value)
        return manifests

    @app.get("/api/v1/data/quality", dependencies=read)
    def source_quality_list(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        rows = store.rows(
            """SELECT run_id,report_sha256,events_sha256,created_at,
           json_extract(report_json,'$.instrument') instrument,
           json_extract(report_json,'$.synthetic') synthetic,
           json_extract(report_json,'$.inputs.dataset_hash') dataset_hash,
           json_extract(report_json,'$.counts') counts,
           json_extract(report_json,'$.source_structural_status') source_structural_status,
           json_extract(report_json,'$.calendar_status') calendar_status,
           json_extract(report_json,'$.profile_status') profile_status,
           json_extract(report_json,'$.requested_period_status') requested_period_status,
           json_extract(report_json,'$.historical_admission') historical_admission
           FROM source_quality_receipts ORDER BY created_at DESC,run_id LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        for row in rows:
            row["counts"] = json.loads(row["counts"])
            row["historical_admission"] = bool(row["historical_admission"])
            row["synthetic"] = bool(row["synthetic"])
        return rows

    def source_quality_record(identity):
        from factory.data.source_quality import SourceQuality

        if not store.rows("SELECT run_id FROM source_quality_receipts WHERE run_id=?", (identity,)):
            raise HTTPException(404, "unknown source quality receipt")
        try:
            service = SourceQuality(root, Catalog(root / "catalog"))
            return service, service.verify(identity)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/v1/data/quality/{identity}", dependencies=read)
    def source_quality_detail(identity: str):
        return source_quality_record(identity)[1]

    @app.get("/api/v1/data/quality/{identity}/events", dependencies=read)
    def source_quality_events(identity: str):
        service, _ = source_quality_record(identity)
        return FileResponse(
            service.directory / identity / "events.jsonl",
            media_type="application/x-ndjson",
            filename="source-quality-" + identity + ".jsonl",
        )

    @app.get("/api/v1/data/quality-attempts", dependencies=read)
    def source_quality_attempts(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.rows(
            "SELECT * FROM source_quality_attempts ORDER BY created_at DESC,attempt_id LIMIT ? OFFSET ?",
            (limit, offset),
        )

    @app.get("/api/v1/input-reviews", dependencies=read)
    def reviewed_inputs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        rows = store.rows(
            "SELECT * FROM reviewed_inputs ORDER BY created_at DESC,review_id LIMIT ? OFFSET ?",
            (limit, offset),
        )
        results = []
        for row in rows:
            body = json.loads(row["body_json"])
            dependencies = [row["review_id"]]
            if row["kind"] == "admission":
                dependencies += [body["profile_review_id"], body["calendar_review_id"]]
            revoked = [
                key
                for key in dependencies
                if store.rows("SELECT 1 FROM input_revocations WHERE review_id=?", (key,))
            ]
            period = body.get("window") or {
                "start_ns": body["effective_start_ns"],
                "end_ns": body["effective_end_ns"],
            }
            results.append(
                {
                    "review_id": row["review_id"],
                    "kind": row["kind"],
                    "reviewer": body["reviewer"],
                    "start_ns": str(period["start_ns"]),
                    "end_ns": str(period["end_ns"]),
                    "revoked_dependencies": revoked,
                    "reference_count": len(
                        {c["document_sha256"] for c in body.get("citations", {}).values()}
                    ),
                    "assumption_fields": [
                        key
                        for key, c in body.get("citations", {}).items()
                        if c["basis"] == "explicit_research_assumption"
                    ],
                    "status": "REVOKED" if revoked else "RECORDED_REQUIRES_EXECUTION_RECHECK",
                }
            )
        return results

    @app.get("/api/v1/input-reviews/{identity}", dependencies=read)
    def reviewed_input_detail(identity: str):
        from factory.data.admission import InputRegistry

        rows = store.rows("SELECT * FROM reviewed_inputs WHERE review_id=?", (identity,))
        if not rows:
            raise HTTPException(404, "unknown reviewed input")
        registry = InputRegistry(root, Catalog(root / "catalog"))
        try:
            if rows[0]["kind"] == "admission":
                registry._check_admission(registry._load(identity, "admission"))
            else:
                registry.reference(identity, rows[0]["kind"])
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return Response(rows[0]["body_json"], media_type="application/json")

    @app.get("/api/v1/audit", dependencies=read)
    def audit(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.rows(
            "SELECT * FROM audit_events ORDER BY event_id DESC LIMIT ? OFFSET ?", (limit, offset)
        )

    if dashboard and Path(dashboard).is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app
