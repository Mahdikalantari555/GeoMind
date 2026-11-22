from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class JobRecord:
    id: str
    type: str
    status: str = "pending"  # pending | running | completed | failed | error
    progress: float = 0.0
    stage: str | None = None
    percent: int | None = None
    detail: str | None = None
    result: Any | None = None
    # Stable code + correlation id only; raw exception text is kept in the
    # server-side log (error_detail) and never exposed through the API/SSE.
    error: str | None = None
    error_id: str | None = None
    error_detail: str | None = field(default=None, repr=False)

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed", "error")

    def public(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "percent": self.percent,
            "detail": self.detail,
        }
        if self.result is not None:
            body["result"] = self.result
        if self.error is not None:
            body["error"] = self.error
        if self.error_id is not None:
            body["error_id"] = self.error_id
        return body


def _accepts_job_id(fn: Callable[..., Any]) -> bool:
    """True when ``fn`` declares a positional ``job_id`` parameter."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for param in sig.parameters.values():
        if (
            param.name == "job_id"
            and param.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ):
            return True
    return False


@dataclass
class JobManager:
    """In-process background job registry.

    Jobs run blocking callables in a threadpool; status is queryable by id.
    Single-user local platform: no persistence, no pruning strategy needed
    beyond a size cap.
    """

    _jobs: dict[str, JobRecord] = field(default_factory=dict)
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _max_records: int = 256
    _loop: asyncio.AbstractEventLoop | None = None
    _closing: bool = False

    def startup(self) -> None:
        """Reopen the registry on app startup (TestClient / server restart)."""
        self._closing = False

    def should_stop(self) -> bool:
        """Cooperative cancellation flag for long-running job callbacks."""
        return self._closing

    async def submit(self, job_type: str, fn: Callable[..., Any]) -> JobRecord:
        """Run `fn` in a background thread; return the job record immediately."""
        from .errors import GeoFrontError

        if self._closing:
            raise GeoFrontError(
                code="gateway_shutting_down",
                message="Gateway is shutting down; no new jobs accepted.",
                status_code=503,
            )
        record = JobRecord(id=uuid.uuid4().hex[:12], type=job_type)

        async with self._lock:
            self._loop = asyncio.get_running_loop()
            # Evict oldest terminal jobs when over the cap. If everything is
            # still running, refuse rather than growing the registry without
            # bound.
            if len(self._jobs) >= self._max_records:
                terminal = [
                    k for k, v in self._jobs.items() if v.status in ("completed", "failed", "error")
                ]
                if not terminal:
                    raise GeoFrontError(
                        code="too_many_jobs",
                        message="Too many active jobs; retry when one finishes.",
                        status_code=429,
                    )
                for key in terminal[: len(self._jobs) - self._max_records + 1]:
                    self._jobs.pop(key, None)
                    self._tasks.pop(key, None)
            self._jobs[record.id] = record

        from .events import get_event_bus

        get_event_bus().publish(
            "job_progress",
            {
                "id": record.id,
                "type": record.type,
                "status": record.status,
                "progress": 0.0,
                "stage": record.stage,
                "percent": record.percent,
                "detail": record.detail,
            },
        )
        get_event_bus().publish(
            "job.progress",
            {
                "id": record.id,
                "type": record.type,
                "status": record.status,
                "progress": 0.0,
                "stage": record.stage,
                "percent": record.percent,
                "detail": record.detail,
            },
        )

        async def _run() -> None:
            record.status = "running"
            get_event_bus().publish(
                "job_progress",
                {
                    "id": record.id,
                    "type": record.type,
                    "status": "running",
                    "progress": 0.0,
                    "stage": record.stage,
                    "percent": record.percent,
                    "detail": record.detail,
                },
            )
            get_event_bus().publish(
                "job.progress",
                {
                    "id": record.id,
                    "type": record.type,
                    "status": "running",
                    "progress": 0.0,
                    "stage": record.stage,
                    "percent": record.percent,
                    "detail": record.detail,
                },
            )
            try:
                if asyncio.iscoroutinefunction(fn):
                    record.result = (
                        await fn(record.id) if _accepts_job_id(fn) else await fn()
                    )
                elif _accepts_job_id(fn):
                    record.result = await asyncio.to_thread(fn, record.id)
                else:
                    record.result = await asyncio.to_thread(fn)
                record.status = "completed"
                record.progress = 1.0
                record.percent = 100
                record.stage = "done"
                get_event_bus().publish(
                    "job_progress",
                    {
                        "id": record.id,
                        "type": record.type,
                        "status": "completed",
                        "progress": 1.0,
                        "stage": "done",
                        "percent": 100,
                        "detail": record.detail,
                        # No job result on the global SSE stream: clients
                        # refetch it from the authenticated jobs endpoint.
                    },
                )
                get_event_bus().publish(
                    "job.progress",
                    {
                        "id": record.id,
                        "type": record.type,
                        "status": "completed",
                        "progress": 1.0,
                        "stage": "done",
                        "percent": 100,
                        "detail": record.detail,
                        # No job result on the global SSE stream: clients
                        # refetch it from the authenticated jobs endpoint.
                    },
                )
            except Exception as exc:  # noqa: BLE001 — surfaced via stable code
                error_id = uuid.uuid4().hex[:12]
                # Full detail stays server-side for diagnosis; the client sees
                # only a stable code and a correlation id it can quote.
                log.error("job %s failed error_id=%s: %s", record.id, error_id, exc)
                record.status = "error"
                record.error = "job_failed"
                record.error_id = error_id
                record.error_detail = str(exc)
                payload = {
                    "id": record.id,
                    "type": record.type,
                    "status": "error",
                    "progress": record.progress,
                    "stage": record.stage,
                    "percent": record.percent,
                    "detail": record.detail,
                    "error": record.error,
                    "error_id": error_id,
                }
                get_event_bus().publish("job_progress", payload)
                get_event_bus().publish("job.progress", payload)
                # Also publish "failed" alias for backwards compat with old clients
                get_event_bus().publish(
                    "job_progress",
                    {
                        "id": record.id,
                        "type": record.type,
                        "status": "failed",
                        "progress": record.progress,
                        "error": record.error,
                        "error_id": error_id,
                    },
                )

        self._tasks[record.id] = asyncio.create_task(_run())
        return record

    def _apply_progress(
        self,
        job_id: str,
        stage: str | None,
        percent: int | None,
        detail: str | None,
    ) -> None:
        """Mutate the record and publish — must run on the owning loop."""
        record = self._jobs.get(job_id)
        if record is None or record.is_terminal:
            return

        if stage is not None:
            record.stage = stage
        if percent is not None:
            record.percent = max(0, min(100, percent))
            record.progress = record.percent / 100.0
        if detail is not None:
            record.detail = detail

        from .events import get_event_bus

        payload = {
            "id": record.id,
            "type": record.type,
            "status": record.status,
            "progress": record.progress,
            "stage": record.stage,
            "percent": record.percent,
            "detail": record.detail,
        }
        get_event_bus().publish("job_progress", payload)
        get_event_bus().publish("job.progress", payload)

    def update_progress(
        self,
        job_id: str,
        *,
        stage: str | None = None,
        percent: int | None = None,
        detail: str | None = None,
    ) -> None:
        """Thread-safe progress update (worker callbacks may call from a thread)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
            if loop is not None and not loop.is_closed():
                loop.call_soon_threadsafe(
                    self._apply_progress, job_id, stage, percent, detail
                )
                return
        self._apply_progress(job_id, stage, percent, detail)

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def wait_for(self, job_id: str, timeout: float = 120.0) -> JobRecord:
        """Block until a job reaches a terminal state (tests / internal use)."""
        import asyncio as _asyncio

        record = self._jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        task = self._tasks.get(job_id)
        if task is not None:
            await _asyncio.wait_for(_asyncio.shield(task), timeout=timeout)
        return record

    async def aclose(self) -> None:
        self._closing = True
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        for task in self._tasks.values():
            with contextlib.suppress(BaseException):
                await task


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager


def reset_job_manager() -> None:
    global _manager
    _manager = None
