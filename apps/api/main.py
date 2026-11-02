"""Single authenticated API. Loopback only until authorized secure exposure."""

import hashlib
import hmac
import json
from pathlib import Path
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
import psutil
from pydantic import BaseModel, ConfigDict, model_validator
from factory.contracts import ExperimentContract, InstrumentSpec, StrategySpec, SYMBOLS, fingerprint
from factory.data import Catalog
from factory.experiments import Store
from factory.ranking import leaderboard
from factory.simulation.ledger import require_execution_version, EXECUTION_VERSION


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
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        )
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
                "ram_available_bytes": psutil.virtual_memory().available,
                "disk_free_bytes": psutil.disk_usage(root).free,
            },
            "hermes": {"configured": False, "required_for_research": False},
        }

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
        execution_version: Literal["adverse-fill/v1", "adverse-fill/v2"] | None = None,
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
        job_id = store.enqueue(
            "research", p.model_dump(mode="json"), p.contract.experiment_hash, actor="api-operator"
        )
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
        return [
            json.loads(p.read_text()) for p in sorted((root / "catalog").glob("*/manifest.json"))
        ]

    @app.get("/api/v1/audit", dependencies=read)
    def audit(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.rows(
            "SELECT * FROM audit_events ORDER BY event_id DESC LIMIT ? OFFSET ?", (limit, offset)
        )

    if dashboard and Path(dashboard).is_dir():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app
