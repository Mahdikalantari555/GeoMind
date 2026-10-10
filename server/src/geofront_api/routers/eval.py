from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import RunEvalRequest
from ..state import get_state

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run", status_code=202)
async def run_eval(req: RunEvalRequest) -> dict[str, object]:
    """Run a benchmark (JSONL) against the active workspace as a background job."""
    state = get_state()
    ws: GeoMemory = state.require_workspace()

    bench_file = Path(req.benchmark_path).expanduser()
    if not bench_file.is_file():
        raise GeoFrontError(
            code="eval_file_not_found",
            message=f"Benchmark file not found: {req.benchmark_path}",
            status_code=404,
        )

    async def _do_eval() -> dict[str, object]:
        async with state.write_lock:
            try:
                res = await run_in_threadpool(ws.run_benchmark, req.benchmark_path, req.config)
                return res.model_dump(mode="json")
            except GeoMemoryError as exc:
                raise RuntimeError(f"Eval run failed: {exc}") from exc

    record = await get_job_manager().submit("eval_run", _do_eval)
    return {"job_id": record.id, "status": record.status}
