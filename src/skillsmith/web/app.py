"""FastAPI application for the Skillsmith review workbench.

Flow: POST documents -> a background job runs ``forge_batch`` -> the client
polls job status -> each generated skill can be edited and approved/discarded ->
download zips only the approved skills, rendered to the chosen formats.

The app is created via ``create_app`` so a stub completer can be injected for
tests (keeping the whole web layer offline-testable, like the rest of the repo).
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from ..batch import forge_batch
from ..ir import SkillIR
from ..llm import Completer
from ..renderers import available_formats, get_renderer

_STATIC = Path(__file__).parent / "static"

# decision defaults per forge status
_DEFAULT_DECISION = {"pass": "approved", "review": "pending"}


@dataclass
class JobSkill:
    index: int
    source: str                 # original filename
    status: str                 # pass | review | rejected | error
    confidence: str | None
    skill: dict | None          # editable SkillIR dump; None if rejected/error
    error: str | None = None
    decision: str = "pending"   # approved | pending | discarded | n/a


@dataclass
class Job:
    id: str
    status: str                 # running | done | error
    formats: list[str]
    sources_dir: Path
    skills: list[JobSkill] = field(default_factory=list)
    error: str | None = None


def _render_bundle(skill: SkillIR, formats: list[str]) -> dict[str, str]:
    """Render one skill to every chosen format; keys are zip-relative paths."""
    bundle: dict[str, str] = {}
    for fmt in formats:
        for rel, content in get_renderer(fmt).render(skill).items():
            bundle[f"{fmt}/{skill.name}/{rel}"] = content
    return bundle


def _run_job(app: FastAPI, job: Job) -> None:
    try:
        items = forge_batch(
            job.sources_dir,
            completer=app.state.completer,
            max_workers=app.state.forge_workers,
        )
        skills: list[JobSkill] = []
        for i, item in enumerate(items):
            if item.error:
                skills.append(JobSkill(i, item.path.name, "error", None, None, item.error, "n/a"))
                continue
            result = item.result
            if result and result.rejected:
                conf = result.final_confidence.value
                skills.append(JobSkill(i, item.path.name, "rejected", conf, None, None, "n/a"))
            elif result and result.skill:
                status = "pass" if result.passed else "review"
                skills.append(
                    JobSkill(
                        index=i,
                        source=item.path.name,
                        status=status,
                        confidence=result.skill.confidence.value,
                        skill=result.skill.model_dump(mode="json"),
                        decision=_DEFAULT_DECISION[status],
                    )
                )
            else:
                skills.append(JobSkill(i, item.path.name, "error", None, None, "no skill produced", "n/a"))
        job.skills = skills
        job.status = "done"
    except Exception as exc:  # noqa: BLE001 - surface any failure to the client
        job.error = f"{type(exc).__name__}: {exc}"
        job.status = "error"


def create_app(completer: Completer | None = None, forge_workers: int = 4) -> FastAPI:
    app = FastAPI(title="Skillsmith", description="Knowledge → agent skills")
    app.state.jobs = {}
    app.state.completer = completer
    app.state.forge_workers = forge_workers

    def _job(job_id: str) -> Job:
        job = app.state.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    def _skill(job: Job, index: int) -> JobSkill:
        for s in job.skills:
            if s.index == index:
                return s
        raise HTTPException(404, "skill not found")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/formats")
    def formats() -> dict:
        return {"formats": available_formats()}

    @app.post("/api/jobs")
    async def create_job(
        files: list[UploadFile] = File(...),
        formats: str = Form(""),
    ) -> dict:
        job_id = uuid.uuid4().hex[:12]
        workdir = Path(tempfile.mkdtemp(prefix=f"skillsmith-{job_id}-"))
        sources = workdir / "sources"
        sources.mkdir()
        for f in files:
            name = Path(f.filename or "upload").name
            (sources / name).write_bytes(await f.read())

        chosen = [x.strip() for x in formats.split(",") if x.strip()] or available_formats()
        job = Job(id=job_id, status="running", formats=chosen, sources_dir=sources)
        app.state.jobs[job_id] = job
        threading.Thread(target=_run_job, args=(app, job), daemon=True).start()
        return {"job_id": job_id, "status": "running"}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = _job(job_id)
        return {
            "job_id": job.id,
            "status": job.status,
            "formats": job.formats,
            "error": job.error,
            "skills": [asdict(s) for s in job.skills],
        }

    @app.put("/api/jobs/{job_id}/skills/{index}")
    def update_skill(job_id: str, index: int, payload: dict = Body(...)) -> dict:
        job = _job(job_id)
        js = _skill(job, index)
        if js.skill is None:
            raise HTTPException(409, "this item produced no editable skill")

        skill_data = payload.get("skill")
        if skill_data is not None:
            try:
                model = SkillIR.model_validate(skill_data)
            except ValidationError as e:
                # e.errors() can embed non-serializable ctx; e.json() is JSON-safe.
                raise HTTPException(422, detail=json.loads(e.json())) from None
            js.skill = model.model_dump(mode="json")
            js.confidence = model.confidence.value
        decision = payload.get("decision")
        if decision:
            js.decision = decision
        return asdict(js)

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str) -> Response:
        job = _job(job_id)
        buf = io.BytesIO()
        exported = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for js in job.skills:
                if js.skill is None or js.decision != "approved":
                    continue
                skill = SkillIR.model_validate(js.skill)
                for path, content in _render_bundle(skill, job.formats).items():
                    zf.writestr(path, content)
                exported += 1
        if exported == 0:
            raise HTTPException(400, "no approved skills to export")
        buf.seek(0)
        return Response(
            buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=skills.zip"},
        )

    return app
