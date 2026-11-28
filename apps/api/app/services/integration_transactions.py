"""Run synchronous Integration writes without blocking the API event loop."""
import asyncio

from anyio import CancelScope
from starlette.concurrency import run_in_threadpool


async def run_integration_write(operation, *args, **kwargs):
    # FastAPI owns the request Session. Once dispatched, let the transaction
    # finish before dependency teardown can close that Session on cancellation.
    with CancelScope(shield=True):
        worker = asyncio.create_task(run_in_threadpool(operation, *args, **kwargs))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            completion = asyncio.gather(worker, return_exceptions=True)
            while not completion.done():
                try:
                    await asyncio.shield(completion)
                except asyncio.CancelledError:
                    continue
            raise
