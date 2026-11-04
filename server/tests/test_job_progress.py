from __future__ import annotations

import asyncio

from geofront_api.events import get_event_bus
from geofront_api.jobs import JobManager


def test_job_progress_fields_and_events() -> None:
    async def _async_test() -> None:
        bus = get_event_bus()
        bus.bind(asyncio.get_running_loop())
        queue = await bus.subscribe()

        mgr = JobManager()

        def work() -> str:
            return "ok"

        record = await mgr.submit("test_task", work)

        # Update progress directly
        mgr.update_progress(record.id, stage="indexing", percent=45, detail="indexed 45 segments")

        updated = mgr.get(record.id)
        assert updated is not None
        assert updated.stage == "indexing"
        assert updated.percent == 45
        assert updated.detail == "indexed 45 segments"
        pub = updated.public()
        assert pub["stage"] == "indexing"
        assert pub["percent"] == 45

        await mgr.wait_for(record.id)
        final = mgr.get(record.id)
        assert final is not None
        assert final.status == "completed"
        assert final.percent == 100
        assert final.stage == "done"

        # Drain queued events
        events: list[dict[str, object]] = []
        while not queue.empty():
            events.append(await queue.get())

        bus.unsubscribe(queue)
        assert any(e.get("event") == "job.progress" for e in events)

    asyncio.run(_async_test())
