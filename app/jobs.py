import json
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


class QueueFull(Exception):
    pass


@dataclass
class Job:
    id: str
    club: str
    status: str
    key: str
    created_at: float
    error: str | None = None


class JobStore:
    def __init__(self, root: Path, ttl_s: float, max_queued: int) -> None:
        self.root = root
        self._ttl_s = ttl_s
        self._max_queued = max_queued
        self._cv = threading.Condition()
        self._jobs: dict[str, Job] = {}
        self._by_key: dict[str, str] = {}
        self._queue: list[str] = []
        self.root.mkdir(parents=True, exist_ok=True)
        self._load()

    def directory(self, job_id: str) -> Path:
        return self.root / job_id

    def get(self, job_id: str) -> Job | None:
        with self._cv:
            return self._jobs.get(job_id)

    def find(self, key: str) -> Job | None:
        with self._cv:
            self._purge()
            return self._live(key)

    def submit(self, club: str, key: str, logo: bytes, suffix: str) -> Job:
        with self._cv:
            self._purge()
            existing = self._live(key)
            if existing:
                return existing
            queued = sum(1 for job in self._jobs.values() if job.status == "queued")
            if queued >= self._max_queued:
                raise QueueFull()
            job = Job(
                id=uuid.uuid4().hex,
                club=club,
                status="queued",
                key=key,
                created_at=time.time(),
            )
            folder = self.directory(job.id)
            folder.mkdir(parents=True, exist_ok=False)
            (folder / f"logo{suffix}").write_bytes(logo)
            self._jobs[job.id] = job
            self._by_key[key] = job.id
            self._queue.append(job.id)
            self._write(job)
            self._cv.notify()
            return job

    def take(self, stop: threading.Event) -> Job | None:
        with self._cv:
            while not self._queue and not stop.is_set():
                self._cv.wait(timeout=30)
                self._purge()
            if stop.is_set() or not self._queue:
                return None
            job = self._jobs[self._queue.pop(0)]
            job.status = "rendering"
            job.error = None
            self._write(job)
            return job

    def mark(self, job_id: str, status: str, error: str | None) -> None:
        with self._cv:
            job = self._jobs[job_id]
            job.status = status
            job.error = error
            if status != "ready":
                output = self.directory(job_id) / "out.mp4"
                if output.exists():
                    output.unlink()
            elif self._by_key.get(job.key) != job_id:
                self._by_key[job.key] = job_id
            self._write(job)

    def wake(self) -> None:
        with self._cv:
            self._cv.notify_all()

    def output(self, job: Job) -> Path:
        return self.directory(job.id) / "out.mp4"

    def logo(self, job: Job) -> Path:
        folder = self.directory(job.id)
        found = [path for path in folder.iterdir() if path.name.startswith("logo.")]
        if len(found) != 1:
            raise FileNotFoundError(job.id)
        return found[0]

    def _live(self, key: str) -> Job | None:
        job_id = self._by_key.get(key)
        if not job_id:
            return None
        job = self._jobs.get(job_id)
        if not job or job.status == "failed":
            return None
        if job.status == "ready" and not self.output(job).is_file():
            return None
        return job

    def _load(self) -> None:
        pending: list[Job] = []
        for folder in self.root.iterdir():
            meta = folder / "job.json"
            if not folder.is_dir() or not meta.is_file():
                continue
            try:
                raw = json.loads(meta.read_text(encoding="utf-8"))
                job = Job(
                    id=str(raw["id"]),
                    club=str(raw["club"]),
                    status=str(raw["status"]),
                    key=str(raw["key"]),
                    created_at=float(raw["createdAt"]),
                    error=raw.get("error"),
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if job.id != folder.name or job.status not in ("queued", "rendering", "ready", "failed"):
                continue
            self._jobs[job.id] = job
            if job.status == "rendering":
                job.status = "queued"
                job.error = None
                output = self.output(job)
                if output.exists():
                    output.unlink()
                self._write(job)
            if job.status == "queued":
                pending.append(job)
        pending.sort(key=lambda job: job.created_at)
        self._queue.extend(job.id for job in pending)
        for job in self._jobs.values():
            if job.status == "failed":
                continue
            if job.status == "ready" and not self.output(job).is_file():
                continue
            current = self._by_key.get(job.key)
            if current is None or self._jobs[current].status != "ready":
                self._by_key[job.key] = job.id

    def _purge(self) -> None:
        cutoff = time.time() - self._ttl_s
        expired = [
            job
            for job in self._jobs.values()
            if job.status not in ("queued", "rendering") and job.created_at < cutoff
        ]
        for job in expired:
            self._jobs.pop(job.id, None)
            if self._by_key.get(job.key) == job.id:
                self._by_key.pop(job.key, None)
            shutil.rmtree(self.directory(job.id), ignore_errors=True)

    def _write(self, job: Job) -> None:
        payload = {
            "id": job.id,
            "club": job.club,
            "status": job.status,
            "key": job.key,
            "createdAt": job.created_at,
            "error": job.error,
        }
        path = self.directory(job.id) / "job.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
