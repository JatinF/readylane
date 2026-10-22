"""HTTP release gate. Liveness does not touch the database."""

import logging
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from readylane import __version__
from readylane.errors import GateError
from readylane.settings import Settings
from readylane.store import Store
from readylane.verify import digest_artifact

log = logging.getLogger("readylane")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_STATUS = {"not_found": 404, "unauthorized": 403, "denied": 403, "conflict": 409, "invalid": 400}


class ChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_id: str
    title: str = Field(min_length=1, max_length=200)


class ArtifactIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact: str


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = (settings if settings is not None else Settings.from_env()).validated()
    store = Store(resolved.database_path)
    print(
        f"readylane listening host={resolved.host} port={resolved.port} db={resolved.database_path}",
        flush=True,
    )
    log.info("listening host=%s port=%s db=%s", resolved.host, resolved.port, resolved.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.store.close()

    app = FastAPI(title="Readylane release gate", version=__version__, lifespan=lifespan)
    app.state.settings = resolved
    app.state.store = store

    @app.exception_handler(GateError)
    def _on_gate_error(_request, exc: GateError):
        return JSONResponse(status_code=_STATUS.get(exc.code, 400), content={"error": exc.code, "detail": exc.message})

    def actor(authorization: str | None = Header(default=None)) -> tuple[str, str]:
        if authorization is None or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="authentication required")
        token = authorization.split(" ", 1)[1].strip()
        if token == resolved.lead_token:
            return resolved.lead_subject, "lead"
        if token == resolved.approver_token:
            return resolved.approver_subject, "approver"
        raise HTTPException(status_code=401, detail="authentication required")

    def require_lead(current=Depends(actor)) -> str:
        subject, role = current
        if role != "lead":
            raise GateError("unauthorized", "lead role required")
        return subject

    def require_approver(current=Depends(actor)) -> str:
        subject, role = current
        if role != "approver":
            raise GateError("unauthorized", "approver role required")
        return subject

    def change_or_404(change_id: str) -> dict:
        if _ID.fullmatch(change_id) is None:
            raise GateError("invalid", "change id is invalid")
        row = store.get(change_id)
        if row is None:
            raise GateError("not_found", "change not found")
        return row

    @app.get("/healthz")
    def healthz():
        return {
            "status": "ok",
            "package": "readylane",
            "version": __version__,
            "customer_cloud": "not-used",
        }

    @app.get("/readyz")
    def readyz():
        try:
            store.ping()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not-ready"})
        return {"status": "ready", "database": "ok"}

    @app.post("/v1/changes", status_code=201)
    def create_change(body: ChangeIn, subject: str = Depends(require_lead)):
        if _ID.fullmatch(body.change_id) is None:
            raise GateError("invalid", "change id is invalid")
        title = body.title.strip()
        if not title:
            raise GateError("invalid", "title is required")
        return store.create(body.change_id, title, subject)

    @app.get("/v1/changes/{change_id}")
    def get_change(change_id: str, _current=Depends(actor)):
        return change_or_404(change_id)

    @app.post("/v1/changes/{change_id}/verify")
    def verify_change(change_id: str, body: ArtifactIn, _subject: str = Depends(require_lead)):
        change_or_404(change_id)
        try:
            digest = digest_artifact(body.artifact)
        except ValueError as exc:
            raise GateError("invalid", str(exc)) from None
        row = store.verify(change_id, digest["sha256"], digest["byte_length"])
        return row

    @app.post("/v1/changes/{change_id}/release")
    def release_change(change_id: str, _subject: str = Depends(require_lead)):
        change_or_404(change_id)
        return store.request_release(change_id)

    @app.post("/v1/changes/{change_id}/decision")
    def decide_change(change_id: str, body: DecisionIn, subject: str = Depends(require_approver)):
        change_or_404(change_id)
        return store.decide(change_id, subject, body.decision)

    return app
