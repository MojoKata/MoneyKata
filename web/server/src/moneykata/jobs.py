"""Long work (requirements S13.8.7): an import, a statement read or a projection run answers
202 with a job, `/ui/api/jobs/{id}`, and the live stream announces its end. Jobs are work state
(schema.md §4.4), kept in memory for a day."""

import datetime as dt
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from . import clock, ids

JobState = Literal["waiting", "running", "done", "failed"]
KEEP = dt.timedelta(days=1)


@dataclass
class Job:
    id: str
    kind: str
    userId: str
    state: JobState = "waiting"
    progress: float = 0.0
    result: Any = None
    error: dict | None = None
    created: dt.datetime = field(default_factory=clock.now)
    finished: dt.datetime | None = None


class Jobs:
    def __init__(self, announce: Callable[[Job], None] | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._announce = announce

    def create(self, kind: str, user_id: str) -> Job:
        job = Job(id=ids.new_id("Job"), kind=kind, userId=user_id)
        with self._lock:
            self._prune()
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str, user_id: str) -> Job | None:
        """A job is visible only to the user who started it."""
        with self._lock:
            job = self._jobs.get(job_id)
        return job if job and job.userId == user_id else None

    def update(self, job: Job, **changes) -> None:
        for k, v in changes.items():
            setattr(job, k, v)
        if job.state in ("done", "failed"):
            job.finished = clock.now()
            if self._announce:
                self._announce(job)

    def _prune(self) -> None:
        cutoff = clock.now() - KEEP
        for k in [k for k, j in self._jobs.items() if j.finished and j.finished < cutoff]:
            del self._jobs[k]
