import asyncio
from contextlib import asynccontextmanager


class SemaphoreManager:
    def __init__(self, max_concurrent: int = 10, per_domain: int = 2):
        if max_concurrent < 1 or per_domain < 1:
            raise ValueError("Concurrency limits must be positive")
        self.global_semaphore = asyncio.Semaphore(max_concurrent)
        self.per_domain = per_domain
        self.domain_semaphores = {}
        self.active_tasks = 0

    @asynccontextmanager
    async def slot(self, domain: str):
        domain_semaphore = self.domain_semaphores.setdefault(
            domain, asyncio.Semaphore(self.per_domain)
        )
        async with self.global_semaphore:
            async with domain_semaphore:
                self.active_tasks += 1
                try:
                    yield
                finally:
                    self.active_tasks -= 1
