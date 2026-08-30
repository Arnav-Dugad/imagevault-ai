import asyncio

from app.worker import tasks


def test_worker_runner_reuses_one_event_loop():
    tasks.close_worker_resources()

    async def current_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    try:
        first = tasks._get_worker_runner().run(current_loop())
        second = tasks._get_worker_runner().run(current_loop())
        assert first is second
    finally:
        tasks.close_worker_resources()
