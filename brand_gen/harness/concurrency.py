"""Concurrency helpers for running async coroutines safely in sync environments."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Run an async coroutine from a synchronous context safely.

    Checks if an event loop is currently running. If one is, executes the
    coroutine in a separate background thread with its own event loop to
    prevent nested event loop runtime errors. Otherwise, runs it via normal
    asyncio.run mechanism.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Running in an active loop environment (e.g. CLI, web server, or notebook).
        # We spawn a background thread with its own event loop to run the coroutine.
        def _run_in_thread() -> T:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_thread)
            return future.result()
    else:
        # Standard sync script context with no running loop.
        return asyncio.run(coro)
