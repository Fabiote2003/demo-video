import hashlib
import logging
import re
import secrets
import threading
import unicodedata
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.jobs import Job, JobStore, QueueFull
from app.render import LogoError, RenderError, logo_kind, prepare_logo, render_demo
from app.settings import LOGO_MAX_BYTES, load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

settings = load_settings()
store = JobStore(settings.data_dir, ttl_s=settings.ttl_days * 86400, max_queued=settings.max_queued)
_stop = threading.Event()


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    ascii_text = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")


def _view(job: Job) -> dict[str, str]:
    body = {"id": job.id, "status": job.status}
    if job.error:
        body["error"] = job.error
    return body


def _authorized(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = f"Bearer {settings.token}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Token inválido")


def _loop() -> None:
    while True:
        job = store.take(_stop)
        if job is None:
            return
        try:
            render_demo(
                club=job.club,
                logo_path=store.logo(job),
                output_path=store.output(job),
                base_path=settings.base_video,
                remotion_dir=settings.remotion_dir,
            )
            store.mark(job.id, "ready", None)
            logging.info("listo %s", job.id)
        except RenderError as exc:
            logging.error("job %s: %s", job.id, exc)
            store.mark(job.id, "failed", str(exc))
        except Exception:
            logging.exception("job %s", job.id)
            store.mark(job.id, "failed", "No se pudo armar el video")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    logos = settings.remotion_dir / "public" / "logos"
    logos.mkdir(parents=True, exist_ok=True)
    for path in logos.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()
    thread = threading.Thread(target=_loop, name="render", daemon=True)
    thread.start()
    yield
    _stop.set()
    store.wake()
    thread.join(timeout=5)


app = FastAPI(lifespan=_lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health() -> JSONResponse:
    ok = settings.base_video.is_file()
    return JSONResponse({"ok": ok}, status_code=200 if ok else 503)


@app.post("/v1/videos", status_code=202, dependencies=[Depends(_authorized)])
async def create_video(
    club: Annotated[str, Form()],
    logo: Annotated[UploadFile, File()],
) -> JSONResponse:
    name = club.strip()
    if len(name) < 2 or len(name) > 150 or any(ord(char) < 32 for char in name) or not _slug(name):
        raise HTTPException(status_code=400, detail="El nombre del club no sirve")
    data = await logo.read(LOGO_MAX_BYTES + 1)
    if len(data) > LOGO_MAX_BYTES:
        raise HTTPException(status_code=400, detail="El logo pesa más de 2 MB")
    kind = logo_kind(data)
    if not kind:
        raise HTTPException(status_code=400, detail="El logo tiene que ser png, jpeg o webp")
    key = hashlib.sha256(name.encode() + b"\0" + data).hexdigest()
    existing = store.find(key)
    if existing:
        return JSONResponse(_view(existing), status_code=202)
    try:
        prepared, suffix = prepare_logo(data, kind)
    except LogoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        job = store.submit(name, key, prepared, suffix)
    except QueueFull as exc:
        raise HTTPException(status_code=429, detail="Hay demasiados videos en cola") from exc
    return JSONResponse(_view(job), status_code=202)


@app.get("/v1/videos/{job_id}", dependencies=[Depends(_authorized)])
def video_status(job_id: str) -> JSONResponse:
    job = _job(job_id)
    return JSONResponse(_view(job))


@app.get("/v1/videos/{job_id}/file", dependencies=[Depends(_authorized)])
def video_file(job_id: str) -> FileResponse:
    job = _job(job_id)
    path = store.output(job)
    if job.status != "ready" or not path.is_file():
        raise HTTPException(status_code=409, detail="El video todavía no está listo")
    return FileResponse(path, media_type="video/mp4", filename=f"quadro_demo_{_slug(job.club)}.mp4")


def _job(job_id: str) -> Job:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="No encuentro ese video")
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="No encuentro ese video")
    return job
