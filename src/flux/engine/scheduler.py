"""Execution Scheduler with strict concurrency limits."""

import asyncio
from typing import Optional


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int = 2):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.max_observed_concurrency = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self.semaphore.acquire()
        async with self._lock:
            self.active_count += 1
            if self.active_count > self.max_observed_concurrency:
                self.max_observed_concurrency = self.active_count

    async def release(self):
        async with self._lock:
            self.active_count = max(0, self.active_count - 1)
        self.semaphore.release()
